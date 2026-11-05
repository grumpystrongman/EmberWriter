"""Optional, entirely offline loudness and peak analysis for narrated tracks.

Measurements are engineering observations, not proof of retailer acceptance.
No media is changed by this module and no external services are contacted.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from .audiobook_jobs import _read as read_job
from .audiobook_local import audio_file
from .audiobook_quality import inspect

# An educational listening target, *not* an ACX or other retailer preset.
TARGET_I = -18.0
TARGET_TP = -2.0
TARGET_LRA = 11.0
MAX_TRACKS = 120
LOUDNORM_JSON = re.compile(r"\{\s*\"input_i\"\s*:\s*\"[^\"]+\".*?\"target_offset\"\s*:\s*\"[^\"]+\"\s*\}", re.S)


def executable() -> str | None:
    return shutil.which("ffmpeg")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _numbers(body: str) -> dict:
    match = LOUDNORM_JSON.search(body)
    if match is None:
        raise ValueError("FFmpeg did not return usable loudness measurements")
    data = json.loads(match.group())
    fields = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    def parse(key: str) -> float | None:
        try:
            num = float(data[key])
        except (ValueError, KeyError, TypeError):
            return None
        return round(num, 2) if math.isfinite(num) else None
    return {key: parse(key) for key in fields}


def analyze_file(path: Path, *, timeout: int = 1200) -> dict:
    ffmpeg = executable()
    if not ffmpeg:
        raise ValueError("Local FFmpeg is required for loudness analysis")
    if not path.is_file():
        raise FileNotFoundError("Narration audio is missing")
    command = [
        ffmpeg, "-nostdin", "-hide_banner", "-i", str(path),
        "-vn", "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, errors="replace",
            timeout=timeout, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError("Local FFmpeg could not measure this audio") from exc
    measured = _numbers(result.stderr)
    return {
        "integrated_lufs": measured["input_i"],
        "true_peak_dbtp": measured["input_tp"],
        "loudness_range_lu": measured["input_lra"],
        "threshold_lufs": measured["input_thresh"],
        "offset_lu": measured["target_offset"],
        "measured": all(measured[key] is not None for key in
                        ("input_i", "input_tp", "input_lra", "input_thresh")),
    }


def report(slug: str) -> dict:
    """Author-triggered analysis; caches by audio hash, not by filenames alone."""
    job = read_job(slug)
    readiness = inspect(slug)
    if not job or job["status"] != "completed" or not readiness["ready"]:
        raise ValueError("Finish and technically verify the current audiobook before measuring loudness")
    chapters = job["chapters"]
    if len(chapters) > MAX_TRACKS:
        raise ValueError("Audiobook has too many chapters for one loudness report")
    from .storage import project_root
    cache_path = project_root(slug) / ".ember" / "audiobook" / "loudness-report.json"
    cached = {}
    if cache_path.is_file():
        try:
            body = json.loads(cache_path.read_text(encoding="utf-8"))
            cached = {x["path"]: x for x in body.get("tracks", []) if isinstance(x, dict)}
        except (ValueError, OSError, KeyError):
            cached = {}
    items = []
    warnings = []
    for chapter in chapters:
        path = audio_file(slug, chapter["filename"])
        digest = _hash(path)
        previous = cached.get(chapter["path"])
        if previous and previous.get("audio_sha256") == digest and previous.get("filename") == path.name:
            track = previous
        else:
            track = {
                "path": chapter["path"], "title": chapter.get("title", chapter["path"]),
                "filename": path.name, "audio_sha256": digest,
                **analyze_file(path),
            }
        if track.get("integrated_lufs") is None:
            warnings.append({"path": chapter["path"], "detail": "Integrated loudness could not be measured; review silence or corrupted audio"})
        elif track["integrated_lufs"] < -24 or track["integrated_lufs"] > -14:
            warnings.append({"path": chapter["path"], "detail": "Chapter loudness falls outside the optional -24 to -14 LUFS inspection band"})
        if track.get("true_peak_dbtp") is None:
            warnings.append({"path": chapter["path"], "detail": "True peak could not be measured"})
        elif track["true_peak_dbtp"] > -1.0:
            warnings.append({"path": chapter["path"], "detail": "High true peak: potential clipping/limited headroom"})
        items.append(track)
    # Reject a report if the author changed either the source or the tracks
    # while expensive audio analysis was running.
    fresh = inspect(slug)
    if not fresh["ready"] or len(fresh["tracks"]) != len(items):
        raise ValueError("Audiobook source or recording changed during analysis; run it again")
    for item in items:
        if _hash(audio_file(slug, item["filename"])) != item["audio_sha256"]:
            raise ValueError("An audio file changed during loudness analysis")
    payload = {
        "status": "measured", "tracks": items, "warnings": warnings,
        "target_lufs": TARGET_I, "true_peak_target_dbtp": TARGET_TP,
        "disclaimer": "Local engineering measurements only. The -18 LUFS / -2 dBTP target is not a retailer certification or ACX compliance preset.",
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)
    return payload
