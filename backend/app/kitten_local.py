"""Optional *native-emotion* CPU TTS line rehearsals via KittenTTS 2.

The 1.7B KittenTTS 2 model is installed by the author under its own license.
EmberWriter never downloads weights automatically, changes project canon,
or sends manuscript or voice data to an external service.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from . import audio_production
from .audiobook_local import _spoken_text
from .storage import project_root, read_text

VOICE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
TAKE_NAME = re.compile(r"^[0-9a-f]{32}\.wav$")
MAX_LINE_CHARS = 1200
_LOCK = threading.RLock()

# Official KittenTTS 2 tags; all other author presets are approximations.
# No nonverbal vocal events are inserted without a separate source-alignment plan.
EMOTION_TAGS = {
    "neutral": "", "joy": "joyful", "excitement": "excited",
    "sadness": "sad", "grief": "sad", "anger": "angry",
    "fear": "nervous", "urgency": "excited", "relief": "tender",
    "determination": "stern", "uncertainty": "contemplative",
    "tenderness": "tender", "sarcasm": "contemplative",
    "surprise": "surprised", "awe": "contemplative",
    "exhaustion": "mundane", "soft": "tender",
}
LICENSE_URL = "https://huggingface.co/KittenML/kitten-tts-2/blob/main/LICENSE.md"


def model_directory() -> Path | None:
    configured = os.environ.get("EMBERWRITER_KITTEN_MODEL_DIR", "").strip()
    if not configured:
        return None
    directory = Path(configured).expanduser()
    return directory if directory.is_absolute() else None


def model_identity() -> str:
    """Cheap installed-weight identity; prevents mixing editions across a batch.

    File sizes and mtime protect the author from accidental model switches.
    They are not a cryptographic guarantee that model weights were unmodified.
    """
    folder = model_directory()
    if folder is None or not (folder / "config.json").is_file():
        raise ValueError("Kitten model folder is missing")
    manifests = []
    for candidate in sorted(folder.rglob("*")):
        if candidate.is_file() and candidate.suffix.lower() in {
            ".safetensors", ".gguf", ".pt", ".bin", ".json",
        }:
            info = candidate.stat()
            manifests.append((str(candidate.relative_to(folder)), info.st_size,
                              info.st_mtime_ns))
    if not manifests:
        raise ValueError("Kitten model directory has no usable weights")
    return hashlib.sha256(json.dumps({
        "directory": str(folder.resolve()), "files": manifests,
    }, sort_keys=True).encode("utf-8")).hexdigest()


def status() -> dict:
    folder = model_directory()
    configured = bool(folder and (folder / "config.json").is_file())
    return {
        "engine": "kitten-tts-2",
        "configured": configured,
        "installed": configured and importlib.util.find_spec("kittenml") is not None,
        "cpu_compatible": True,
        "native_emotion_conditioning": True,
        "offline_only": True,
        "auto_download": False,
        "model_directory": str(folder) if folder else "",
        "package_installed": importlib.util.find_spec("kittenml") is not None,
        "license": "Stellon Labs Community License (not Apache 2.0 model weights)",
        "license_url": LICENSE_URL,
        "notes": "Optional 1.7B model. Authors install and accept weight licensing independently. "
                 "CPU Python inference may be slow; official C++ backend is faster but is not "
                 "integrated here. Emotion steering is beta, not guaranteed.",
    }


@lru_cache(maxsize=1)
def _engine(folder: str):
    from kittenml import KittenTTS
    # A LOCAL path prevents the convenience API from fetching weights from HF.
    # CPU explicitly selected even on machines with a discrete GPU.
    return KittenTTS(folder, device="cpu", weights="emb4")


def voice_ids() -> list[str]:
    info = status()
    if not info["installed"]:
        raise ValueError("Install the optional KittenTTS package and configure a local model folder")
    with _LOCK:
        model = _engine(info["model_directory"])
        return sorted(str(voice) for voice in model.available_voices)


def library(slug: str) -> dict:
    return dict(audio_production.load(slug).get("kitten_voices", {}))


@audio_production.synchronized
def save_profile(slug: str, character: str, voice: str) -> dict:
    name = character.strip()
    if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise ValueError("Invalid character name")
    if not VOICE_NAME.fullmatch(voice):
        raise ValueError("Choose a built-in Kitten voice")
    if voice not in voice_ids():
        raise ValueError("Voice not available in the configured Kitten model")
    state = audio_production.load(slug)
    profiles = state.setdefault("kitten_voices", {})
    if name not in profiles and len(profiles) >= audio_production.MAX_CHARACTERS + 1:
        raise ValueError("Kitten voice library is full")
    profiles[name] = {"voice_id": voice}
    audio_production._write(slug, state)
    return profiles[name]


def line_prompt(text: str, emotion: str, energy: int) -> tuple[str, str]:
    if emotion not in EMOTION_TAGS:
        raise ValueError("Choose a supported performance emotion")
    if type(energy) is not int or not 1 <= energy <= 5:
        raise ValueError("Energy must be 1–5")
    if not text.strip() or len(text) > MAX_LINE_CHARS:
        raise ValueError("Choose a spoken line of 1–1200 characters")
    tag = EMOTION_TAGS[emotion]
    # Stable decoding is quieter/more repeatable, expressive decoding takes
    # bigger risks. This does not guarantee intensity follows a linear scale.
    preset = "stable" if energy <= 2 or not tag else "expressive"
    return (f"[{tag}] {text}" if tag else text), preset


def _cue(slug: str, path: str, start: int) -> tuple[dict, str]:
    text = _spoken_text(read_text(slug, path))
    from .audio_director import load_or_compile
    state = audio_production.load(slug)
    names = sorted(set(state.get("kitten_voices", {}))
                   | set(state.get("kokoro_voices", {}))
                   | set(state.get("neural_voices", {}))
                   | set(state.get("character_voices", {})) | {"Narrator"})
    record = load_or_compile(
        project_root(slug) / ".ember" / "audio-director" /
        (Path(path).stem + ".performance.json"), text, names,
        state.get("chapter_casts", {}).get(path, []))
    row = next((item for item in record["spans"]
                if item.get("kind") == "dialogue" and item["start"] == start), None)
    if not row or not row.get("speaker") or row["speaker"] == "Narrator":
        raise ValueError("Assign a character to this line in Audio Director")
    if row["speaker"] not in state.get("kitten_voices", {}):
        raise ValueError("Assign a local Kitten voice to this character before rehearsing")
    if len(row["text"]) > MAX_LINE_CHARS:
        raise ValueError("Selected dialogue is too long for one proof take")
    return row, text


def _folder(slug: str) -> Path:
    return project_root(slug) / ".ember" / "kitten-rehearsals"


def render_line(slug: str, path: str, start: int) -> dict:
    import numpy as np
    import soundfile as sf
    from .expressive_prosody import apply_expression

    if not status()["installed"]:
        raise ValueError("KittenTTS 2 is not installed locally")
    row, source = _cue(slug, path, start)
    profile = library(slug)[row["speaker"]]
    direction = row.get("performance", {})
    emotion = direction.get("emotion", "neutral")
    energy = direction.get("energy", 3)
    spoken, preset = line_prompt(row["text"], emotion, energy)
    folder = model_directory()
    assert folder is not None
    with _LOCK:
        engine = _engine(str(folder))
        if profile["voice_id"] not in engine.available_voices:
            raise ValueError("Saved Kitten voice no longer exists")
        samples = engine.generate(
            spoken, voice=profile["voice_id"], preset=preset)
        if engine.sample_rate != 24000:
            raise ValueError("Kitten returned an unexpected audio sample rate")
    shaped = apply_expression(
        np.asarray(samples, dtype=np.float32),
        gain_db=(int(energy) - 3) * 0.30,
    )
    if not 0 < len(shaped) <= 24000 * 180:
        raise ValueError("Kitten rehearsal returned empty or excessively long audio")
    if _spoken_text(read_text(slug, path)) != source:
        raise ValueError("Manuscript changed during rehearsal. Discarding take.")
    target_dir = _folder(slug)
    target_dir.mkdir(parents=True, exist_ok=True)
    identifier = uuid4().hex
    target = target_dir / (identifier + ".wav")
    stage = target_dir / (identifier + ".tmp.wav")
    sf.write(stage, shaped, 24000, subtype="PCM_16")
    stage.replace(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "id": identifier, "filename": target.name, "status": "unapproved_rehearsal",
        "engine": "kitten-tts-2", "voice_id": profile["voice_id"],
        "path": path, "start": start, "text": row["text"], "emotion": emotion,
        "energy": energy, "preset": preset, "prompt": spoken,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "audio_sha256": digest, "publication_approved": False,
        "license_review_required": True,
        "model_directory": str(folder),
    }
    (target_dir / (identifier + ".json")).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    return {key: val for key, val in manifest.items() if key != "model_directory"}


def take_file(slug: str, filename: str) -> Path:
    if not TAKE_NAME.fullmatch(filename):
        raise ValueError("Invalid rehearsal filename")
    path = _folder(slug) / filename
    if not path.is_file():
        raise FileNotFoundError(filename)
    return path
