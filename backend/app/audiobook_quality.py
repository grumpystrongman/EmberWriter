"""Offline audiobook QC: source freshness, WAV integrity and package readiness.

Never claims that a voice performs well. Zero external requests and no model calls.
Legacy renders without source hashes are treated as unverified, not current.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path

from .audiobook_jobs import _fingerprint
from .audiobook_jobs import _read as read_job
from .audiobook_local import audio_file, list_renders
from .storage import get_project

MIN_DURATION = 0.1


def _file_diagnostics(file: Path) -> dict:
    if file.suffix.lower() == ".wav":
        try:
            with wave.open(str(file), "rb") as stream:
                channels = stream.getnchannels()
                rate = stream.getframerate()
                frames = stream.getnframes()
                width = stream.getsampwidth()
                if channels < 1 or channels > 8 or rate < 8000 or width not in (1, 2, 3, 4):
                    raise ValueError("Unexpected WAV channel, rate or sample width")
                duration = frames / rate
                # Full silence checks only inspect bounded audio samples, never the entire file.
                # For PCM formats, all-zero samples are trivially silent; unsigned 8-bit silence
                # is 0x80, so this is deliberately an advisory rather than a true RMS meter.
                sample = stream.readframes(min(frames, rate * 2))
                byte_marker = b"\x80" if width == 1 else b"\x00"
                possible_silence = bool(sample) and sample.count(byte_marker) == len(sample)
                return {
                    "format": "wav", "seconds": round(duration, 2), "sample_rate": rate,
                    "channels": channels, "bit_depth": width * 8,
                    "possibly_silent_intro": possible_silence,
                    "valid": duration >= MIN_DURATION,
                }
        except (wave.Error, EOFError, OSError, ValueError) as exc:
            return {"format": "wav", "valid": False, "reason": f"Unreadable WAV: {type(exc).__name__}"}
    if file.suffix.lower() == ".mp3":
        # MP3 validity and duration require ffprobe. An installed ffmpeg executable
        # alone is not sufficient. Unknown must never be reported as verified.
        import shutil
        probe = shutil.which("ffprobe")
        if not probe:
            return {"format": "mp3", "valid": None, "reason": "Install ffprobe for MP3 duration/integrity checks"}
        try:
            result = subprocess.run(
                [probe, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_name,sample_rate,channels:format=duration",
                 "-of", "json", str(file)],
                capture_output=True, text=True, timeout=35, check=True,
            )
            import json
            payload = json.loads(result.stdout)
            audio = (payload.get("streams") or [{}])[0]
            duration = float(payload.get("format", {}).get("duration", 0))
            valid = audio.get("codec_name") == "mp3" and math.isfinite(duration) and duration >= MIN_DURATION
            return {
                "format": "mp3", "valid": valid, "seconds": round(duration, 2) if math.isfinite(duration) else None,
                "sample_rate": int(audio.get("sample_rate") or 0),
                "channels": int(audio.get("channels") or 0),
            }
        except (OSError, subprocess.SubprocessError, ValueError, IndexError, TypeError, KeyError):
            return {"format": "mp3", "valid": False, "reason": "ffprobe could not read the MP3 stream"}
    return {"valid": False, "reason": "Unsupported narration format"}


def inspect(slug: str) -> dict:
    get_project(slug)
    job = read_job(slug)
    renders = {track["source_path"]: track for track in list_renders(slug)}
    selected = job["chapters"] if job else []
    from .audio_production import load as load_settings
    from .audio_production import snapshot
    settings = load_settings(slug)
    from .proof_approval import proof_status
    config_changed = bool(job and job.get("settings_signature") and
                          job["settings_signature"] != snapshot(slug)["signature"])
    issues: list[dict] = []
    tracks: list[dict] = []
    total_seconds = 0.0
    for chapter in selected:
        source = chapter["path"]
        entry = renders.get(source)
        track = {"path": source, "title": chapter.get("title", source), "status": chapter["status"],
                 "filename": chapter.get("filename", ""), "seconds": None, "checks": []}
        if chapter["status"] != "rendered":
            track["checks"].append("Chapter has not been narrated")
        elif not entry or entry["filename"] != chapter["filename"]:
            track["checks"].append("Narration file missing from this project's approved render manifest")
        else:
            try:
                fresh = _fingerprint(slug, source) == chapter["fingerprint"]
            except (OSError, ValueError, FileNotFoundError):
                fresh = False
            if not fresh:
                track["checks"].append("Manuscript has changed since narration was queued")
            if config_changed:
                track["checks"].append("Pronunciation dictionary or narrator profiles changed since narration")
            if job.get("settings_signature") and entry.get("settings_signature") != job["settings_signature"]:
                track["checks"].append("Audio does not match the narration configuration used for this batch")
            if not entry.get("source_hash"):
                track["checks"].append("Legacy audio has no source hash; re-render for provenance")
            elif entry["source_hash"] != chapter["fingerprint"]:
                track["checks"].append("Narration does not correspond to the queued manuscript revision")
            details = _file_diagnostics(audio_file(slug, chapter["filename"]))
            track["format"] = details.get("format", "")
            track["seconds"] = details.get("seconds")
            track["sample_rate"] = details.get("sample_rate")
            track["channels"] = details.get("channels")
            if details.get("valid") is False:
                track["checks"].append(details.get("reason", "Damaged or empty audio"))
            elif details.get("valid") is None:
                track["checks"].append(details.get("reason", "Audio integrity unverified"))
            approval = proof_status(slug, source, chapter["filename"])
            track["proof_approval"] = approval
            if not approval["approved"]:
                track["checks"].append("Full-recording proof-listening not approved: " + approval["reason"])
            if details.get("possibly_silent_intro"):
                track["checks"].append("Opening two seconds may be silent; listen before distributing")
            if isinstance(details.get("seconds"), (float, int)):
                total_seconds += details["seconds"]
        for warning in track["checks"]:
            issues.append({"path": source, "detail": warning})
        tracks.append(track)
    for note in settings["proof_notes"]:
        if note["status"] != "resolved" and any(chapter["path"] == note["path"] and
                chapter.get("filename") == note.get("filename") for chapter in selected):
            issues.append({"path": note["path"], "detail": "Open proof-listening note at " +
                           str(note["seconds"]) + "s: " + note["note"][:120]})
    if not job:
        issues.append({"path": "", "detail": "No whole-book audiobook job exists"})
    elif job["status"] != "completed":
        issues.append({"path": "", "detail": "Whole-book narration has not completed"})
    return {
        "status": job["status"] if job else "not_started",
        "m4b_available": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "ready": not issues and bool(tracks),
        "tracks": tracks,
        "issues": issues,
        "duration_seconds": round(total_seconds, 2),
        "verified_tracks": sum(not track["checks"] for track in tracks),
        "total_tracks": len(tracks),
        "disclaimer": "Readiness includes author-attested full playback and source alignment bound to exact manuscript and audio hashes. This is not automatic speech-to-text verification or retailer certification.",
    }
