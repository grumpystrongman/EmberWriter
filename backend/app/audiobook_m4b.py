"""Compile a locally narrated Binder book into a chapter-marked M4B.

Offline FFmpeg-only, author-triggered, no text-to-speech or external calls.
Source revision and audio integrity checks must pass before packaging.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .audiobook_jobs import _read as read_job
from .audiobook_local import _folder, audio_file
from .audiobook_quality import inspect
from .storage import get_project


def _metadata_text(chapters: list[dict], durations: list[float], title: str) -> str:
    # FFMETADATA escaping matters for book/chapter titles entered by authors.
    def escape(value: str) -> str:
        return (value.replace("\\", "\\\\").replace("=", "\\=")
                .replace(";", "\\;").replace("#", "\\#")
                .replace("\r", " ").replace("\n", " ")[:250])
    lines = [";FFMETADATA1", "title=" + escape(title), "genre=Audiobook"]
    offset = 0
    for chapter, duration in zip(chapters, durations):
        millis = max(1, round(duration * 1000))
        lines.extend((
            "[CHAPTER]", "TIMEBASE=1/1000", f"START={offset}",
            f"END={offset + millis}", "title=" + escape(chapter.get("title") or chapter["path"]),
        ))
        offset += millis
    return "\n".join(lines) + "\n"


def export_m4b(slug: str) -> Path:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("Local FFmpeg and FFprobe must be installed to create M4B")
    state = read_job(slug)
    if not state or state["status"] != "completed":
        raise ValueError("Complete the audiobook narration before generating M4B")
    report = inspect(slug)
    if not report["ready"]:
        raise ValueError("Audiobook technical readiness has outstanding issues; run Check audio readiness first")
    chapters = state["chapters"]
    if not chapters or len(chapters) != len(report["tracks"]):
        raise ValueError("Audiobook chapter count changed during compilation")
    durations = [track["seconds"] for track in report["tracks"]]
    if any(not isinstance(seconds, (int, float)) or seconds <= 0 for seconds in durations):
        raise ValueError("Every audio chapter must have a verified duration for M4B chapters")
    sources = [audio_file(slug, chapter["filename"]) for chapter in chapters]
    folder = _folder(slug)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "current-book-narration.m4b"
    # Stage the output so a failed encoder never overwrites the prior artifact.
    with tempfile.TemporaryDirectory(prefix="ember-m4b-", dir=folder) as working:
        scratch = Path(working)
        playlist = scratch / "chapters.txt"
        # FFmpeg concat demuxer supports absolute, source-local paths.
        playlist.write_text(
            "".join("file '" + str(source.resolve()).replace("\\", "/").replace("'", "'\\''") + "'\n"
                    for source in sources),
            encoding="utf-8",
        )
        metadata = scratch / "chapters.ffmeta"
        metadata.write_text(
            _metadata_text(chapters, durations, get_project(slug)["name"]),
            encoding="utf-8",
        )
        output = scratch / "narration.m4b"
        subprocess.run(
            [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(playlist),
             "-f", "ffmetadata", "-i", str(metadata),
             "-map", "0:a:0", "-map_metadata", "1", "-map_chapters", "1",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             "-f", "ipod", "-movflags", "+faststart", str(output)],
            capture_output=True, text=True, timeout=1200, check=True,
        )
        if not output.exists() or output.stat().st_size < 1024:
            raise ValueError("FFmpeg produced no usable M4B audio")
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_name:chapter=start_time,end_time:format=duration",
             "-of", "json", str(output)],
            capture_output=True, text=True, timeout=45, check=True,
        )
        info = json.loads(probe.stdout)
        if not any(stream.get("codec_name") == "aac" for stream in info.get("streams", [])):
            raise ValueError("FFmpeg output has no AAC audio stream")
        if len(info.get("chapters", [])) != len(chapters):
            raise ValueError("M4B chapter markers do not match the narration batch")
        # Recheck source freshness after encoding (novels may be edited while audio compiles).
        second_report = inspect(slug)
        if not second_report["ready"] or second_report["total_tracks"] != len(chapters):
            raise ValueError("The source manuscript or audio changed during compilation")
        output.replace(target)
    return target
