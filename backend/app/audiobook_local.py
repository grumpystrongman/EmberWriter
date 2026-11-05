"""Offline audiobook rendering from author's manuscript, using Windows SAPI voices.

No hosted TTS, no text upload, no automatic rewrite. One chapter per request.
Output is locally stored under the current project only; chapter WAV is preserved
even when FFmpeg is not installed. This is a basic narration path, not a mastered
multi-actor audiobook production engine.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from .storage import get_project, project_root, read_text

MAX_AUDIO_WORDS = 12000
_RENDER_LOCKS: dict[str, threading.RLock] = {}
SAPI_SCRIPT = Path(__file__).with_name("audio_sapi.ps1")
VOICE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 ._-]{0,100}$")
FILENAME_PATTERN = re.compile(r"^[0-9a-f]{16}\.(?:mp3|wav)$")


def _time() -> str:
    return datetime.now(timezone.utc).isoformat()


def _folder(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "audiobook"


def _manifest(slug: str) -> Path:
    return _folder(slug) / "manifest.json"


def _read_manifest(slug: str) -> dict:
    path = _manifest(slug)
    if not path.exists():
        return {"chapters": [], "version": 1}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or not isinstance(loaded.get("chapters"), list):
        raise ValueError("Audiobook manifest is invalid")
    return loaded


def _save_manifest(slug: str, manifest: dict) -> None:
    path = _manifest(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _spoken_text(text: str) -> str:
    """Convert simple manuscript Markdown to plain narration, not a full MD renderer."""
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", "", text)
    text = re.sub(r"[*_`~]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def available_chapters(slug: str) -> list[dict]:
    project = get_project(slug)
    options = []
    for path in sorted(project["files"]):
        if not path.startswith("manuscript/") or not path.lower().endswith((".md", ".txt")):
            continue
        text = _spoken_text(read_text(slug, path))
        words = len(text.split())
        options.append({"path": path, "words": words, "narratable": words >= 5})
    return options[:250]


def available_voices() -> list[str]:
    if sys.platform != "win32":
        return []
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "try {$s.GetInstalledVoices() | ForEach-Object {$_.VoiceInfo.Name}} "
        "finally {$s.Dispose()}"
    )
    output = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                             "-Command", script],
                            capture_output=True, text=True, timeout=25, check=True)
    return [line.strip() for line in output.stdout.splitlines() if line.strip()]


def list_renders(slug: str) -> list[dict]:
    manifest = _read_manifest(slug)
    folder = _folder(slug)
    return [entry for entry in manifest["chapters"]
            if isinstance(entry, dict)
            and FILENAME_PATTERN.fullmatch(str(entry.get("filename", "")))
            and (folder / entry["filename"]).is_file()]


def render(slug: str, source: str, voice: str = "", rate: int = -1, *,
           rules: list[dict] | None = None, settings_signature: str = "",
           casts: list[dict] | None = None) -> dict:
    # A concurrent manual render and a whole-book batch must not corrupt the
    # per-project manifest or create conflicting output files.
    with _RENDER_LOCKS.setdefault(slug, threading.RLock()):
        return _render_unlocked(slug, source, voice, rate, rules=rules,
                                settings_signature=settings_signature, casts=casts)


def _render_unlocked(slug: str, source: str, voice: str = "", rate: int = -1, *,
                     rules: list[dict] | None = None, settings_signature: str = "",
                     casts: list[dict] | None = None) -> dict:
    if sys.platform != "win32":
        raise NotImplementedError("Offline Windows narration is currently supported on Windows only")
    sources = {item["path"]: item for item in available_chapters(slug)}
    if source not in sources:
        raise ValueError("Choose a manuscript chapter in this project")
    if isinstance(rate, bool) or not isinstance(rate, int) or not -5 <= rate <= 5:
        raise ValueError("Narration speed must be an integer from -5 to 5")
    if voice and not VOICE_PATTERN.fullmatch(voice):
        raise ValueError("Invalid installed voice name")
    if voice and voice not in available_voices():
        raise ValueError("The selected offline voice is not installed")
    from .audio_production import snapshot, spoken_replacements, cast_segments
    settings = snapshot(slug)
    if rules is None:
        rules = settings["pronunciations"]
        settings_signature = settings["signature"]
    elif not settings_signature:
        raise ValueError("A narration rule snapshot needs its configuration signature")
    text = _spoken_text(read_text(slug, source))
    casting = casts if casts is not None else settings.get("chapter_casts", {}).get(source, [])
    segments = cast_segments(text, casting, voice, rules) if casting else []
    if casting:
        installed = set(available_voices())
        if any(segment["voice"] not in installed for segment in segments if segment["voice"]):
            raise ValueError("A chapter character voice is no longer installed")
    spoken = spoken_replacements(text, rules)
    if not 5 <= len(text.split()) <= MAX_AUDIO_WORDS:
        raise ValueError("Narration requires 5 to 12,000 words per chapter")
    source_hash = hashlib.sha256(read_text(slug, source).encode("utf-8")).hexdigest()
    fingerprint = hashlib.sha256((voice + "\n" + str(rate) + "\n" + source + "\n" + text + "\n" + spoken + "\n" + settings_signature).encode("utf-8")).hexdigest()[:16]
    folder = _folder(slug)
    folder.mkdir(parents=True, exist_ok=True)
    wav = folder / (fingerprint + ".wav")
    mp3 = folder / (fingerprint + ".mp3")
    if not mp3.is_file() and not wav.is_file():
        with tempfile.TemporaryDirectory(prefix="ember-audio-") as staging:
            input_path = Path(staging) / "chapter.txt"
            staging_wav = Path(staging) / "narration.wav"
            input_path.write_text(spoken, encoding="utf-8")
            if segments:
                segments_path = Path(staging) / "segments.json"
                segments_path.write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
            args = ["powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", str(SAPI_SCRIPT),
                    "-InputPath", str(input_path), "-OutputPath", str(staging_wav)]
            if voice:
                args.extend(["-Voice", voice])
            args.extend(["-Rate", str(rate)])
            if segments:
                args.extend(["-SegmentsPath", str(segments_path)])
            subprocess.run(args, capture_output=True, text=True, timeout=900, check=True)
            if not staging_wav.is_file() or staging_wav.stat().st_size < 44:
                raise RuntimeError("Local narration did not produce a valid wave file")
            shutil.move(str(staging_wav), str(wav))
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-y", "-i",
                                str(wav), "-codec:a", "libmp3lame", "-b:a", "192k",
                                str(mp3)], capture_output=True, timeout=180, check=True)
                if mp3.is_file() and mp3.stat().st_size > 1024:
                    wav.unlink()
                else:
                    mp3.unlink(missing_ok=True)
            except (OSError, subprocess.SubprocessError):
                mp3.unlink(missing_ok=True)
    # Narration may run for many minutes; never certify audio as the current
    # edition when the chapter changed during speech synthesis.
    if hashlib.sha256(read_text(slug, source).encode("utf-8")).hexdigest() != source_hash:
        raise ValueError("Manuscript changed while narration was running; re-render after reviewing edits")
    output = mp3 if mp3.is_file() else wav
    chapter = {"source_path": source, "filename": output.name, "voice": voice or "system-default",
               "rate": rate, "source_hash": source_hash, "settings_signature": settings_signature,
               "bytes": output.stat().st_size, "words": len(text.split()), "rendered_at": _time()}
    manifest = _read_manifest(slug)
    manifest["chapters"] = [ch for ch in manifest["chapters"]
                            if ch.get("source_path") != source] + [chapter]
    _save_manifest(slug, manifest)
    return chapter


def audio_file(slug: str, filename: str) -> Path:
    if not FILENAME_PATTERN.fullmatch(filename):
        raise ValueError("Invalid audio filename")
    if filename not in {entry["filename"] for entry in list_renders(slug)}:
        raise FileNotFoundError("Audio file is not in the current project")
    return _folder(slug) / filename


def archive(slug: str) -> Path:
    tracks = list_renders(slug)
    if not tracks:
        raise ValueError("Render at least one chapter before exporting an audiobook")
    from .audio_production import snapshot
    current_settings = snapshot(slug)["signature"]
    for track in tracks:
        if not track.get("source_hash") or track["source_hash"] != hashlib.sha256(read_text(slug, track["source_path"]).encode("utf-8")).hexdigest():
            raise ValueError(f"Chapter {track['source_path']} changed or lacks source provenance; re-render before export")
        if track.get("settings_signature") != current_settings:
            raise ValueError("Narration dictionary or chapter voice settings changed; re-render before export")
    folder = _folder(slug)
    target = folder / "audiobook-chapters.zip"
    staging = folder / "audiobook-chapters.zip.tmp"
    with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_STORED) as output:
        for track in tracks:
            output.write(folder / track["filename"], arcname=track["filename"])
        output.writestr("manifest.json", json.dumps({"tracks": tracks}, ensure_ascii=False, indent=2))
    staging.replace(target)
    return target
