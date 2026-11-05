"""Offline ACX/Audible *technical preflight*, not retailer acceptance.

Specification source: https://help.acx.com/s/article/what-are-the-acx-audio-submission-requirements
ACX article updated April 15, 2026. Always confirm current specifications
with the retailer before publishing. This report cannot judge acting quality.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from .audio_mastering import analyze_file, _hash
from .audiobook_local import audio_file
from .audiobook_jobs import _read as read_job
from .audiobook_quality import inspect

ACX_PROFILE = {
    "id": "acx-2026-04-15",
    "name": "ACX / Audible technical preflight",
    "synthetic_voice_policy": "Unauthorized text-to-speech or AI narration is prohibited by ACX. EmberWriter SAPI outputs require explicit retailer authorization.",
    "source": "https://help.acx.com/s/article/what-are-the-acx-audio-submission-requirements",
    "published": "2026-04-15",
    "rms_min_dbfs": -23.0,
    "rms_max_dbfs": -18.0,
    "sample_peak_max_dbfs": -3.0,
    "noise_floor_max_dbfs": -60.0,
    "sample_rate_hz": 44100,
    "minimum_kbps": 192,
    "channels": (1, 2),
}


def _probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValueError("Install local FFprobe for retailer audio preflight")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=35,
        )
        stream = json.loads(result.stdout)["streams"][0]
        return {
            "codec": stream.get("codec_name"),
            "duration_seconds": float(json.loads(result.stdout).get("format", {}).get("duration") or 0),
            "sample_rate_hz": int(stream.get("sample_rate") or 0),
            "channels": int(stream.get("channels") or 0),
            "kbps": round(int(stream.get("bit_rate") or 0) / 1000),
        }
    except (OSError, subprocess.SubprocessError, KeyError, IndexError, ValueError, TypeError) as exc:
        raise ValueError("FFprobe could not inspect the retailer track") from exc


def _constant_bitrate(path: Path) -> bool | None:
    """Probe a bounded 30-second packet sample; None means inconclusive."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        run = subprocess.run(
            [ffprobe, "-v", "error", "-read_intervals", "%+30",
             "-select_streams", "a:0", "-show_entries", "packet=size,duration_time",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True, timeout=40,
        )
        rates = []
        for line in run.stdout.splitlines()[:1200]:
            fields = line.strip().split(",")
            if len(fields) != 2:
                continue
            # ffprobe reports packet columns in its own canonical order; both
            # orientations are supported for older builds.
            a, b = fields
            try:
                size, seconds = (int(a), float(b)) if "." in b else (int(b), float(a))
            except (ValueError, TypeError):
                continue
            if size > 0 and seconds > 0 and math.isfinite(seconds):
                rates.append(size * 8 / seconds)
        if len(rates) < 40:
            return None
        rates.sort()
        median = rates[len(rates) // 2]
        # MP3 CBR frame padding may differ by one byte; use 4% tolerance.
        stable = sum(abs(rate - median) <= median * 0.04 for rate in rates)
        return stable / len(rates) >= 0.98
    except (OSError, subprocess.SubprocessError):
        return None


def check_track(path: Path, *, measured: dict | None = None) -> dict:
    """Check measurable limits on the exact encoded file."""
    info = _probe(path)
    audio = analyze_file(path) if measured is None else measured
    checks = {}
    def value(name: str, passed: bool | None, observed, requirement: str):
        checks[name] = {"passed": passed, "observed": observed, "requirement": requirement}

    value("duration", 0 < info["duration_seconds"] <= 7200, round(info["duration_seconds"], 2), "No chapter file longer than 120 minutes")
    value("encoding", info["codec"] == "mp3", info["codec"], "MP3")
    value("sample_rate", info["sample_rate_hz"] == 44100,
          info["sample_rate_hz"], "44,100 Hz")
    value("channels", info["channels"] in (1, 2), info["channels"], "mono or stereo")
    value("bitrate", info["kbps"] >= 192, info["kbps"], "192 kbps or higher")
    cbr = _constant_bitrate(path) if info["codec"] == "mp3" else False
    value("constant_bitrate", cbr, cbr, "MP3 constant bitrate")
    rms = audio.get("rms_dbfs")
    value("rms", None if rms is None else -23 <= rms <= -18, rms, "-23 to -18 dBFS RMS")
    peak = audio.get("sample_peak_dbfs")
    value("sample_peak", None if peak is None else peak < -3, peak, "less than -3 dBFS")
    noise = audio.get("noise_floor_estimate_dbfs")
    value("noise_residual", None if noise is None else noise < -60,
          noise, "below -60 dBFS in quiet passages (advisory estimate)")
    issues = [name for name, check in checks.items() if check["passed"] is not True]
    return {
        "filename": path.name, "audio_sha256": _hash(path), "checks": checks,
        "technical_preflight_passed": not issues, "issues": issues,
        "requires_human_review": True,
    }


def report(slug: str) -> dict:
    status = inspect(slug)
    if not status["ready"]:
        raise ValueError("Complete source verification and author proof approval before retailer preflight")
    job = read_job(slug)
    if not job:
        raise ValueError("No audiobook production exists")
    tracks = [check_track(audio_file(slug, ch["filename"])) for ch in job["chapters"]]
    channels = {row["checks"]["channels"]["observed"] for row in tracks}
    consistent = len(channels) == 1
    return {
        "profile": ACX_PROFILE, "tracks": tracks,
        "channel_format_consistent": consistent,
        "technical_preflight_passed": bool(tracks) and all(
            x["technical_preflight_passed"] for x in tracks) and consistent,
        "submission_eligible": False,
        "submission_blocker": "ACX prohibits unauthorized TTS/AI narration; this app renders Windows SAPI synthetic voices. Obtain explicit ACX authorization or use human narration before submitting.",
        "manual_requirements": [
            "Separate opening and closing credits, naming title, author and narrator",
            "Narrated chapter header in each individually uploaded chapter file",
            "Room tone, performances, artifacts, and complete listening require human QC",
            "Separate chapter files and ACX-compatible ASCII filenames",
            "Confirm cover, copyright metadata, retail sample, and distribution rights",
        ],
        "retailer_certified": False,
        "disclaimer": "Local conservative technical preflight only. ACX Audio Lab and retailer QA remain authoritative; residual noise estimate may be inconclusive.",
    }
