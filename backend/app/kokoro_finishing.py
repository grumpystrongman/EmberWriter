"""Author-owned neural chapter proof, retakes, and complete-book WAV export.

Separate from retailer mastering. All approvals are audio-byte-specific and
source-/voice-setting-bound, and retakes revoke approval for the affected chapter.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import wave
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import kokoro_book
from .local_resources import reservation

_EXPORT_NAME = re.compile(r"^neural-audiobook-[0-9a-f]{32}\.zip$")


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _chapter(job: dict, path: str) -> tuple[int, dict]:
    for index, chapter in enumerate(job["chapters"]):
        if chapter["path"] == path:
            return index, chapter
    raise FileNotFoundError("This manuscript chapter is not in the neural batch")


def _audio_state(slug: str, job: dict, chapter: dict) -> tuple[Path, float, str]:
    if chapter["status"] != "rendered_unapproved" or not chapter["filename"]:
        raise ValueError("Chapter needs complete neural narration before proof approval")
    filename = chapter["filename"]
    source = kokoro_book._directory(slug) / job["id"] / filename
    if not source.is_file():
        raise FileNotFoundError("Neural chapter recording is missing")
    # Never trust filename alone: detect externally edited or truncated audio.
    with wave.open(str(source), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 24000):
            raise ValueError("Neural recording has an unexpected WAV format")
        duration = wav.getnframes() / wav.getframerate()
    if duration <= 0:
        raise ValueError("Neural recording contains no audio")
    return source, duration, _digest(source)


def proof_status(slug: str) -> dict:
    job = kokoro_book._read(slug)
    if not job:
        return {"exists": False, "approved": 0, "total": 0, "ready": False, "chapters": []}
    stale = ""
    try:
        kokoro_book._current(slug, job)
    except (ValueError, FileNotFoundError, OSError) as exc:
        stale = str(exc)
    rows = []
    for chapter in job["chapters"]:
        record = chapter.get("proof_approval", {})
        valid = False
        reason = "Not approved"
        if stale:
            reason = stale
        elif isinstance(record, dict) and record:
            try:
                _, duration, digest = _audio_state(slug, job, chapter)
                valid = (record.get("audio_sha256") == digest
                         and record.get("source_sha256") == chapter["source_sha256"]
                         and record.get("settings_sha256") == job["settings_sha256"]
                         and abs(record.get("duration_seconds", -1) - duration) < .02)
                if not valid:
                    reason = "Recorded audio or proof evidence changed"
            except (OSError, ValueError, FileNotFoundError, wave.Error) as exc:
                reason = str(exc)
        rows.append({"path": chapter["path"], "title": chapter["title"],
                     "approved": valid, "reason": "" if valid else reason,
                     "filename": chapter["filename"], "status": chapter["status"]})
    ready = (not stale and job["status"] == "completed"
             and bool(rows) and all(row["approved"] for row in rows))
    return {"exists": True, "batch_id": job["id"], "approved": sum(r["approved"] for r in rows),
            "total": len(rows), "ready": ready, "stale": bool(stale),
            "stale_reason": stale, "chapters": rows,
            "notice": "Proof approval is an author's full-listen attestation, not automated "
                      "speech-to-text completeness verification or retailer certification."}


def approve(slug: str, path: str, listened_seconds: float,
            full_listen: bool, source_aligned: bool) -> dict:
    if not (full_listen and source_aligned):
        raise ValueError("Confirm full listening and line-by-line source alignment")
    if isinstance(listened_seconds, bool) or not isinstance(listened_seconds, (int, float)):
        raise TypeError("Enter the playback duration actually listened to")
    job = kokoro_book._read(slug)
    if not job:
        raise ValueError("Generate a neural audiobook batch first")
    kokoro_book._current(slug, job)
    _, chapter = _chapter(job, path)
    _, duration, digest = _audio_state(slug, job, chapter)
    if not .95 * duration <= listened_seconds <= 1.2 * duration:
        raise ValueError("Listen to the complete recording before approving")
    chapter["proof_approval"] = {
        "audio_sha256": digest, "source_sha256": chapter["source_sha256"],
        "settings_sha256": job["settings_sha256"],
        "duration_seconds": duration, "listened_seconds": float(listened_seconds),
        "full_listen": True, "source_aligned": True,
        "approved_at": datetime.now(UTC).isoformat(),
    }
    kokoro_book._atomic_json(kokoro_book._jobfile(slug), job)
    return proof_status(slug)


def revoke(slug: str, path: str) -> dict:
    job = kokoro_book._read(slug)
    if not job:
        raise ValueError("No neural audiobook batch")
    _, chapter = _chapter(job, path)
    chapter.pop("proof_approval", None)
    kokoro_book._atomic_json(kokoro_book._jobfile(slug), job)
    return proof_status(slug)


async def retake(slug: str, path: str, segment: int) -> dict:
    """Author explicitly rerenders one segment using frozen voice settings."""
    if isinstance(segment, bool) or not isinstance(segment, int):
        raise TypeError("Choose an integer segment number")
    async with reservation():
        job = kokoro_book._read(slug)
        if not job or job["status"] != "completed":
            raise ValueError("Finish the neural draft before requesting retakes")
        kokoro_book._current(slug, job)
        chapter_index, chapter = _chapter(job, path)
        if not 0 <= segment < chapter["count"]:
            raise ValueError("Segment number is outside this chapter")
        index = chapter["first"] + segment
        item = job["chunks"][index]
        if item["status"] != "rendered":
            raise ValueError("This segment has not yet been recorded")
        # Rerender the source segment, then rebuild the whole affected chapter.
        # The original chapter stays available until the replacement assembles.
        new_hash = await asyncio.to_thread(kokoro_book._render_part, slug, job, index)
        kokoro_book._current(slug, job)
        item["sha256"] = new_hash
        chapter.pop("proof_approval", None)
        chapter["filename"] = await asyncio.to_thread(
            kokoro_book._assemble, slug, job, chapter_index
        )
        chapter["status"] = "rendered_unapproved"
        kokoro_book._atomic_json(kokoro_book._jobfile(slug), job)
        return {"path": path, "segment": segment, "status": "retaken_unapproved",
                "proof": proof_status(slug)}


def segment_list(slug: str, path: str) -> dict:
    job = kokoro_book._read(slug)
    if not job:
        raise ValueError("No neural audiobook batch")
    kokoro_book._current(slug, job)
    _, chapter = _chapter(job, path)
    return {"path": path, "segments": [
        {"index": index, "speaker": item["speaker"], "text": item["text"][:400],
         "status": item["status"]}
        for index, item in enumerate(
            job["chunks"][chapter["first"]:chapter["first"] + chapter["count"]]
        )
    ]}


def export(slug: str) -> dict:
    """Build a lossless, proof-approved archival ZIP of every chapter WAV."""
    checked = proof_status(slug)
    if not checked["ready"]:
        raise ValueError("Finish and explicitly proof-approve every current chapter first")
    job = kokoro_book._read(slug)
    if not job:
        raise ValueError("No neural audiobook batch")
    kokoro_book._current(slug, job)
    folder = kokoro_book._directory(slug) / job["id"]
    name = f"neural-audiobook-{job['id']}.zip"
    output = folder / name
    staging = folder / (name + ".tmp")
    manifest = {"format": "EmberWriter approved WAV chapter archive",
                "batch_id": job["id"], "engine": "kokoro-onnx",
                "retailer_certified": False, "mastered": False,
                "chapters": []}
    with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=True) as bundle:
        for i, chapter in enumerate(job["chapters"], 1):
            wav, duration, digest = _audio_state(slug, job, chapter)
            if digest != chapter["proof_approval"]["audio_sha256"]:
                raise ValueError("Chapter changed since author approval")
            arcname = f"chapter-{i:03d}.wav"
            bundle.write(wav, arcname)
            manifest["chapters"].append({
                "title": chapter["title"], "source_path": chapter["path"],
                "file": arcname, "seconds": round(duration, 3),
                "audio_sha256": digest, "source_sha256": chapter["source_sha256"],
                "approved_at": chapter["proof_approval"]["approved_at"],
            })
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    # Refuse a stale edition if source or approval changed during packaging.
    if not proof_status(slug)["ready"]:
        staging.unlink(missing_ok=True)
        raise ValueError("Approvals or manuscript changed during export")
    staging.replace(output)
    return {"filename": name, "chapters": len(job["chapters"]),
            "bytes": output.stat().st_size,
            "sha256": _digest(output), "format": "approved_wav_chapter_zip",
            "retailer_certified": False}


def export_file(slug: str, filename: str) -> Path:
    if not _EXPORT_NAME.fullmatch(filename):
        raise ValueError("Invalid neural audiobook archive name")
    job = kokoro_book._read(slug)
    if not job or filename != f"neural-audiobook-{job['id']}.zip":
        raise FileNotFoundError("Archive does not belong to this production batch")
    if not proof_status(slug)["ready"]:
        raise ValueError("Audio approval is stale; review the current edition")
    result = kokoro_book._directory(slug) / job["id"] / filename
    if not result.is_file():
        raise FileNotFoundError("Approved chapter archive is missing")
    return result


def _ffmeta(value: str) -> str:
    """Escape FFmpeg metadata values without allowing new directives."""
    return (value.replace("\\", "\\\\").replace("=", "\\=")
            .replace(";", "\\;").replace("#", "\\#")
            .replace("\r", " ").replace("\n", " "))


def export_m4b(slug: str) -> dict:
    """Encode author-approved WAV chapters into a chapter-marked AAC/M4B.

    This is a playable listening edition, not distributor mastering or a
    guarantee that any retailer accepts synthetic narration.
    """
    import shutil
    import subprocess
    from uuid import uuid4

    checked = proof_status(slug)
    if not checked["ready"]:
        raise ValueError("Finish and proof-approve every current neural chapter before M4B encoding")
    job = kokoro_book._read(slug)
    if not job:
        raise ValueError("No neural audiobook batch")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("Local FFmpeg and FFprobe are required to create an M4B")
    folder = kokoro_book._directory(slug) / job["id"]
    name = f"neural-audiobook-{job['id']}.m4b"
    output = folder / name
    nonce = uuid4().hex
    playlist = folder / f"concat-{nonce}.txt"
    metadata = folder / f"chapters-{nonce}.ffmeta"
    staging = folder / f"encode-{nonce}.m4b"
    audio_files = []
    meta_lines = [";FFMETADATA1", "title=EmberWriter Author-Approved Audiobook", ""]
    position_ms = 0
    for chapter in job["chapters"]:
        wav, _duration, digest = _audio_state(slug, job, chapter)
        if digest != chapter["proof_approval"]["audio_sha256"]:
            raise ValueError("Chapter recording was modified after author approval")
        audio_files.append(wav)
        with wave.open(str(wav), "rb") as track:
            samples = track.getnframes()
            sample_rate = track.getframerate()
        length_ms = round(samples * 1000 / sample_rate)
        meta_lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                       f"START={position_ms}", f"END={position_ms + length_ms}",
                       "title=" + _ffmeta(chapter["title"]), ""]
        position_ms += length_ms
    # FFconcat paths use FFmpeg's own quoting rules, not cmd.exe interpolation.
    def quote_file(path: Path) -> str:
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        return "file '" + escaped + "'"

    try:
        playlist.write_text("ffconcat version 1.0\n"
                            + "\n".join(map(quote_file, audio_files)) + "\n", encoding="utf-8")
        metadata.write_text("\n".join(meta_lines), encoding="utf-8")
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-f", "concat", "-safe", "0", "-i", str(playlist),
                   "-f", "ffmetadata", "-i", str(metadata),
                   "-map", "0:a:0", "-map_metadata", "1", "-map_chapters", "1",
                   "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
                   "-movflags", "+faststart", str(staging)]
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=7200)
        report = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_name,sample_rate,channels:chapter=start_time,end_time",
             "-of", "json", str(staging)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        details = json.loads(report.stdout)
        streams = details.get("streams", [])
        if (not streams or streams[0].get("codec_name") != "aac"
                or int(streams[0].get("sample_rate", 0)) != 44100
                or len(details.get("chapters", [])) != len(job["chapters"])):
            raise ValueError("Encoded M4B failed chapter-navigation or audio format verification")
        if not proof_status(slug)["ready"]:
            raise ValueError("Audio approval became stale during M4B encoding")
        staging.replace(output)
    except subprocess.CalledProcessError as exc:
        raise ValueError("FFmpeg could not produce a valid M4B: "
                         + (exc.stderr or "")[-250:]) from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("M4B encoding exceeded the local time limit") from exc
    finally:
        playlist.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
        staging.unlink(missing_ok=True)
    return {"filename": name, "chapters": len(job["chapters"]),
            "sha256": _digest(output), "bytes": output.stat().st_size,
            "codec": "aac", "sample_rate": 44100,
            "format": "author_approved_chapter_marked_m4b",
            "retailer_certified": False, "mastered": False}


def m4b_file(slug: str, filename: str) -> Path:
    if not re.fullmatch(r"neural-audiobook-[0-9a-f]{32}\.m4b", filename):
        raise ValueError("Invalid M4B filename")
    job = kokoro_book._read(slug)
    if not job or filename != f"neural-audiobook-{job['id']}.m4b":
        raise FileNotFoundError("M4B belongs to a different production batch")
    if not proof_status(slug)["ready"]:
        raise ValueError("Current manuscript or voice approval is stale")
    result = kokoro_book._directory(slug) / job["id"] / filename
    if not result.is_file():
        raise FileNotFoundError("M4B must be generated after full approval")
    return result
