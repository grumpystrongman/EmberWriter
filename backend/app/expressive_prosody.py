"""CPU-first author-directed prosody for Kokoro, independent of manuscript text.

Emotion is a *performance preset*, not a claim of Fish-quality model conditioning.
Tempo is fed to Kokoro; pitch is post-processed with FFmpeg's Rubber Band filter
when available. No voice conversion, voice cloning, or invented breath audio.
"""
from __future__ import annotations

import math
import shutil
import subprocess
from functools import lru_cache

import numpy as np

PROSODY_VERSION = 1

# Tempo, pitch in semitones, gain dB, post-line silence in milliseconds.
# Deliberately subtle: much stronger DSP transformations sound unnatural.
PRESETS: dict[str, tuple[float, float, float, int]] = {
    "neutral": (1.00, 0.00, 0.0, 160),
    "joy": (1.045, 0.45, 0.4, 125),
    "excitement": (1.085, 0.65, 0.8, 100),
    "sadness": (0.930, -0.40, -0.8, 240),
    "grief": (0.905, -0.55, -1.1, 275),
    "anger": (1.055, -0.35, 0.8, 105),
    "fear": (1.075, 0.40, -0.2, 120),
    "urgency": (1.095, 0.15, 0.7, 85),
    "relief": (0.965, -0.20, -0.2, 205),
    "determination": (0.985, -0.25, 0.5, 145),
    "uncertainty": (0.960, 0.20, -0.3, 190),
    "tenderness": (0.935, -0.30, -0.6, 230),
    "sarcasm": (0.960, -0.35, -0.3, 210),
    "surprise": (1.065, 0.55, 0.2, 130),
    "awe": (0.940, 0.10, -0.2, 240),
    "exhaustion": (0.910, -0.30, -1.0, 260),
    "soft": (0.930, -0.15, -2.2, 210),
}


def direction_settings(emotion: str = "neutral", energy: int = 3,
                       base_speed: float = 1.0) -> dict:
    if emotion not in PRESETS:
        raise ValueError("Unsupported expression preset")
    if type(energy) is not int or not 1 <= energy <= 5:
        raise ValueError("Expression energy must be 1–5")
    if not isinstance(base_speed, (int, float)) or not math.isfinite(base_speed):
        raise ValueError("Invalid voice speed")
    tempo, pitch, gain, pause = PRESETS[emotion]
    # Energy is the intensity of the direction, not a universal speed slider.
    intensity = 0.65 + 0.175 * (energy - 1)
    tempo = 1 + (tempo - 1) * intensity + (energy - 3) * 0.025
    pitch *= intensity
    gain *= intensity
    pause = round(160 + (pause - 160) * intensity - (energy - 3) * 12)
    return {
        "speed": round(max(0.70, min(1.40, float(base_speed) * tempo)), 3),
        "pitch_semitones": round(pitch, 3),
        "gain_db": round(gain, 3),
        "pause_after_ms": max(55, min(400, pause)),
        "energy": energy,
        "emotion": emotion,
        "prosody_version": PROSODY_VERSION,
    }


@lru_cache(maxsize=1)
def rubberband_available() -> bool:
    executable = shutil.which("ffmpeg")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-filters"],
            capture_output=True, timeout=8, check=False,
        )
        return result.returncode == 0 and b"rubberband" in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def apply_expression(samples: np.ndarray, pitch_semitones: float = 0.0,
                     gain_db: float = 0.0, sample_rate: int = 24000) -> np.ndarray:
    """Apply restrained CPU acoustics without adding or removing spoken text.

    If a pitch change was requested, require the quality-preserving Rubber Band
    FFmpeg filter; a pitch-destroying resampling fallback is intentionally absent.
    """
    if sample_rate != 24000:
        raise ValueError("Expressive audiobook processor requires 24 kHz audio")
    if not -2.0 <= pitch_semitones <= 2.0 or not -6 <= gain_db <= 6:
        raise ValueError("Expression settings exceed safe audio bounds")
    raw = np.asarray(samples, dtype=np.float32)
    if raw.ndim != 1 or not raw.size or not np.isfinite(raw).all():
        raise ValueError("Speech samples must be a finite mono waveform")
    if abs(pitch_semitones) < 0.005:
        result = raw * np.float32(10 ** (gain_db / 20))
    else:
        executable = shutil.which("ffmpeg")
        if not executable or not rubberband_available():
            raise ValueError("Expressive pitch requires FFmpeg with the Rubber Band filter. "
                             "Install the optional audio tools or choose neutral delivery.")
        ratio = 2 ** (pitch_semitones / 12)
        arguments = [
            executable, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
            "-af", f"rubberband=pitch={ratio:.8f}",
            "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "pipe:1",
        ]
        try:
            output = subprocess.run(
                arguments, input=raw.tobytes(), capture_output=True,
                timeout=70, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Local pitch processing failed") from exc
        if output.returncode or len(output.stdout) < 16 or len(output.stdout) % 4:
            raise ValueError("Local pitch processing did not return valid audio")
        result = np.frombuffer(output.stdout, dtype=np.float32).copy()
        result *= np.float32(10 ** (gain_db / 20))
    if not np.isfinite(result).all():
        raise ValueError("Expressive processing returned invalid audio")
    # Guard against clipping; preserve dynamic range when possible.
    peak = float(np.max(np.abs(result)))
    if peak > 0.975:
        result = result * np.float32(0.975 / peak)
    return np.asarray(result, dtype=np.float32)


def capabilities() -> dict:
    return {
        "engine": "kokoro-onnx",
        "cpu_compatible": True,
        "expressions": list(PRESETS),
        "energy_levels": [1, 2, 3, 4, 5],
        "native_emotion_conditioning": False,
        "tempo_control": True,
        "pitch_processing": "rubberband" if rubberband_available() else "unavailable",
        "fish_equivalent": False,
        "notes": "Author-selected emotional presets vary pacing, light pitch, level, and pauses. "
                 "These are acoustic approximations, not native emotional acting. "
                 "Pitch processing needs a compatible local FFmpeg; neutral works without it.",
    }
