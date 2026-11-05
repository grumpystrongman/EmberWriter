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
import sys
from array import array
from pathlib import Path

from .audiobook_jobs import _read as read_job
from .audiobook_local import audio_file
from .audiobook_quality import inspect

# An educational listening target, *not* an ACX or other retailer preset.
TARGET_I = -18.0
TARGET_TP = -2.0
TARGET_LRA = 11.0
MAX_TRACKS = 120
ANALYZER_VERSION = 3  # Independent residual noise estimate added; invalidate older cache
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


def _technical_pcm_levels(path: Path, *, timeout: int) -> dict:
    """FFmpeg-measured overall RMS and intervals below a known threshold.

    Do NOT treat astats Noise_floor as ambient microphone noise. It describes
    the entire waveform and can be near the peak even for a pure sine wave.
    """
    ffmpeg = executable()
    if not ffmpeg:
        raise ValueError("Local FFmpeg is required for RMS analysis")
    try:
        run = subprocess.run(
            [ffmpeg, "-nostdin", "-hide_banner", "-v", "info",
             "-i", str(path), "-vn", "-af",
             "astats=metadata=0:reset=0,silencedetect=noise=-50dB:d=0.4",
             "-f", "null", "-"],
            capture_output=True, text=True, errors="replace",
            timeout=timeout, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("FFmpeg could not inspect narration RMS or quiet passages") from exc
    text = run.stderr
    overall = text.rsplit("Overall", 1)[-1]
    def reading(pattern):
        found = re.search(pattern, overall)
        if not found:
            return None
        try:
            value = float(found.group(1))
        except ValueError:
            return None
        return round(value, 2) if math.isfinite(value) else None
    rms = reading(r"RMS level dB:\s*([-+\w.]+)")
    rms_peak = reading(r"RMS peak dB:\s*([-+\w.]+)")
    sample_peak = reading(r"Peak level dB:\s*([-+\w.]+)")
    starts = [float(item) for item in re.findall(r"silence_start:\s*([\d.]+)", text)]
    ends = [float(item) for item in re.findall(r"silence_end:\s*([\d.]+)", text)]
    # Only complete intervals are counted. Silence remaining at the end
    # can be estimated separately by a future timeline-based listener.
    complete = [end - start for start, end in zip(starts, ends) if end >= start]
    return {
        "rms_dbfs": rms,
        "rms_peak_dbfs": rms_peak,
        "sample_peak_dbfs": sample_peak,
        "quiet_intervals": len(complete),
        "longest_quiet_seconds": round(max(complete, default=0), 2),
        "quiet_threshold_dbfs": -50,
        "quiet_minimum_seconds": 0.4,
    }



def _residual_noise(path: Path, *, timeout: int = 1200) -> dict:
    """Measure the residual signal in quiet windows, independently of speech RMS.

    This estimates an audible low-level residual, not proof of microphone room
    tone: compression, noise gating, and music can all change the result.
    Digital silence is intentionally excluded. Nothing is uploaded.
    """
    ffmpeg = executable()
    if not ffmpeg:
        raise ValueError("Local FFmpeg is required for residual-noise analysis")
    # 250ms at 8 kHz mono, signed 16-bit PCM. Process a bounded stream rather
    # than loading a full novel's audio into memory.
    window_samples = 2000
    proc = subprocess.Popen(
        [ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    eligible = []
    total = 0
    digital_silent = 0
    import time
    deadline = time.monotonic() + timeout
    try:
        assert proc.stdout is not None
        while True:
            if time.monotonic() > deadline:
                raise ValueError("Residual-noise analysis timed out")
            raw = proc.stdout.read(window_samples * 2)
            if not raw:
                break
            if len(raw) < window_samples * 2:
                break
            values = array("h")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            total += 1
            squares = sum(int(x) * int(x) for x in values)
            if squares == 0:
                digital_silent += 1
                continue
            rms = 20 * math.log10(math.sqrt(squares / len(values)) / 32768)
            peak = 20 * math.log10(max(abs(x) for x in values) / 32768)
            # Require very quiet, nonzero audio and exclude transients. This
            # does not confuse a full-volume pure tone with background noise.
            if -85 <= rms <= -42 and peak <= -35:
                eligible.append(rms)
        if proc.wait(timeout=max(1, deadline-time.monotonic())) != 0:
            raise ValueError("FFmpeg could not decode the residual signal")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("FFmpeg could not measure the residual signal") from exc
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stdout:
            proc.stdout.close()
    result = {
        "noise_floor_status": "insufficient_quiet_samples",
        "noise_floor_estimate_dbfs": None,
        "noise_floor_sample_seconds": round(len(eligible) * 0.25, 2),
        "digital_silence_seconds": round(digital_silent * 0.25, 2),
        "noise_floor_method": "nonzero quiet-window PCM RMS, 250ms windows, 8kHz mono",
    }
    if len(eligible) >= 4:
        eligible.sort()
        # Median of quietest fifth: avoids being skewed by a few louder gaps.
        tail = eligible[:max(1, math.ceil(len(eligible) * 0.20))]
        result["noise_floor_estimate_dbfs"] = round(tail[len(tail)//2], 2)
        result["noise_floor_status"] = "estimated_residual"
    return result


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
    technical = _technical_pcm_levels(path, timeout=timeout)
    residual = _residual_noise(path, timeout=timeout)
    return {
        **technical,
        **residual,
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
            if body.get("analyzer_version") == ANALYZER_VERSION:
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
        if track.get("noise_floor_status") != "estimated_residual":
            warnings.append({"path": chapter["path"], "detail": "Noise floor cannot be estimated without a sustained nonzero quiet passage; manually inspect room tone"})
        elif track["noise_floor_estimate_dbfs"] > -60:
            warnings.append({"path": chapter["path"], "detail": "Elevated quiet-passage residual signal; listen for hiss, hum, or other background noise"})
        if track.get("rms_dbfs") is None:
            warnings.append({"path": chapter["path"], "detail": "Overall RMS level could not be measured"})
        if (track.get("longest_quiet_seconds") or 0) > 10.0:
            warnings.append({"path": chapter["path"], "detail": "A passage longer than ten seconds falls below -50 dBFS; listen for an unintended gap"})
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
        "status": "measured", "analyzer_version": ANALYZER_VERSION, "tracks": items, "warnings": warnings,
        "target_lufs": TARGET_I, "true_peak_target_dbtp": TARGET_TP,
        "disclaimer": "Residual noise is an estimate from nonzero quiet passages, not verified microphone room tone; inspect by ear. -18 LUFS / -2 dBTP is not retailer certification.",
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)
    return payload
