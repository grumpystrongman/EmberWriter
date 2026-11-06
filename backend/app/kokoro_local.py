"""Offline, optional Kokoro ONNX author-led scene rehearsals.

Unlike finished audiobook tracks, these are experimental human-review drafts.
No cloud API, automatic authoring, cloning, approvals, or publication side effects.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from . import audio_production
from .audiobook_local import _spoken_text
from .expressive_prosody import PRESETS, apply_expression, direction_settings
from .storage import project_root, read_text

TAKE_NAME = re.compile(r"^[0-9a-f]{32}\.wav$")
VOICE_NAME = re.compile(r"^[a-z]{2}_[a-z]+$")
MAX_SCENE_CHARS = 1200
MAX_SCENE_SEGMENTS = 32
_LOCK = threading.RLock()


def model_paths() -> tuple[Path, Path]:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    folder = base / "EmberWriter" / "models" / "kokoro"
    return folder / "kokoro-v1.0.onnx", folder / "voices-v1.0.bin"


def status() -> dict:
    model, voices = model_paths()
    installed = model.is_file() and model.stat().st_size > 1_000_000 and voices.is_file()
    result = {"engine": "kokoro-onnx", "installed": bool(installed),
              "model_path": str(model), "voices_path": str(voices),
              "voice_ids": [], "offline_only": True}
    if installed:
        try:
            import numpy as np
            with np.load(voices, allow_pickle=False) as voice_bank:
                result["voice_ids"] = sorted(voice_bank.files)
        except (ImportError, OSError, ValueError):
            result["installed"] = False
    return result


def library(slug: str) -> dict:
    return dict(audio_production.load(slug).get("kokoro_voices", {}))


@audio_production.synchronized
def save_profile(slug: str, character: str, voice_id: str, speed: float = 1.0) -> dict:
    character = character.strip()
    if not character or len(character) > 100 or any(ord(c) < 32 for c in character):
        raise ValueError("Character name must be 1-100 printable characters")
    if not VOICE_NAME.fullmatch(voice_id):
        raise ValueError("Choose a Kokoro voice from the installed voice list")
    voices = status()["voice_ids"]
    if voice_id not in voices:
        raise ValueError("Kokoro model/voice files are missing or selected voice is unavailable")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.7 <= speed <= 1.4:
        raise ValueError("Kokoro speaking speed must be between 0.7 and 1.4")
    data = audio_production.load(slug)
    profiles = data.setdefault("kokoro_voices", {})
    if character not in profiles and len(profiles) >= audio_production.MAX_CHARACTERS + 1:
        raise ValueError("Kokoro voice library is full")
    profiles[character] = {"voice_id": voice_id, "speed": float(speed)}
    audio_production._write(slug, data)
    return profiles[character]


@lru_cache(maxsize=1)
def _engine(model: str, voices: str):
    from kokoro_onnx import Kokoro
    return Kokoro(model, voices)


def _manifest_dir(slug: str) -> Path:
    return project_root(slug) / ".ember" / "kokoro-rehearsals"


def scene_plan(slug: str, path: str, start: int, end: int) -> dict:
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (start, end)):
        raise ValueError("Scene selection offsets must be integers")
    text = _spoken_text(read_text(slug, path))
    if not 0 <= start < end <= len(text) or end - start > MAX_SCENE_CHARS:
        raise ValueError("Select a contiguous 1-1200 character scene in the spoken manuscript")
    settings = audio_production.load(slug)
    spans = list(settings.get("chapter_casts", {}).get(path, []))
    # Read-only proof of author-edited Audio Director cues. Do not allow
    # heuristic suggestions to overwrite an explicit manual cast.
    performance_file = project_root(slug) / ".ember" / "audio-director" / (
        Path(path).stem + ".performance.json")
    if performance_file.is_file():
        record = json.loads(performance_file.read_text(encoding="utf-8"))
        if record.get("source_sha256") == hashlib.sha256(text.encode("utf-8")).hexdigest():
            for row in record.get("spans", []):
                if row.get("kind") != "dialogue" or not row.get("speaker"):
                    continue
                if not (0 <= row["start"] < row["end"] <= len(text)):
                    continue
                if text[row["start"]:row["end"]] != row.get("text"):
                    continue
                existing = next((item for item in spans
                                 if item["start"] == row["start"] and item["end"] == row["end"]), None)
                if existing is not None:
                    existing = dict(existing)
                    existing["performance"] = row.get("performance", {})
                    spans = [existing if (item["start"], item["end"]) ==
                             (row["start"], row["end"]) else item for item in spans]
                elif not any(item["start"] < row["end"] and item["end"] > row["start"]
                             for item in spans):
                    spans.append({"start": row["start"], "end": row["end"],
                                  "text": row["text"], "character": row["speaker"],
                                  "performance": row.get("performance", {})})
    spans.sort(key=lambda item: item["start"])
    if any(s["start"] < end and s["end"] > start and
           (s["start"] < start or s["end"] > end) for s in spans):
        raise ValueError("Scene boundaries must not split a manually cast dialogue line")
    cursor = start
    planned = []
    for span in spans:
        if span["start"] < start or span["end"] > end:
            continue
        if not cursor <= span["start"] < span["end"] or text[span["start"]:span["end"]] != span["text"]:
            raise ValueError("A cast line changed: review the manuscript and reassign it")
        if cursor < span["start"]:
            planned.append({"speaker": "Narrator", "text": text[cursor:span["start"]],
                            "performance": {}})
        if not span.get("character"):
            raise ValueError("Scene rehearsal requires named characters, not one-off Windows voices")
        planned.append({"speaker": span["character"], "text": span["text"],
                        "performance": span.get("performance", {})})
        cursor = span["end"]
    if cursor < end:
        planned.append({"speaker": "Narrator", "text": text[cursor:end], "performance": {}})
    planned = [item for item in planned if item["text"].strip()]
    if len(planned) > MAX_SCENE_SEGMENTS:
        raise ValueError("Limit a single rehearsal to 32 voice segments")
    voices = settings.get("kokoro_voices", {})
    missing = sorted({item["speaker"] for item in planned if item["speaker"] not in voices})
    if missing:
        raise ValueError("Assign Kokoro voices to: " + ", ".join(missing))
    for item in planned:
        item.update(voices[item["speaker"]])
        direction = item.pop("performance")
        emotion = direction.get("emotion", "neutral")
        energy = direction.get("energy", 3)
        if type(energy) is not int or not 1 <= energy <= 5:
            energy = 3
        item.update(direction_settings(emotion if emotion in PRESETS else "neutral",
                                       energy, float(item["speed"])))
    identity = hashlib.sha256(json.dumps({
        "source": text, "start": start, "end": end, "parts": planned,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"path": path, "start": start, "end": end, "segments": planned,
            "source_sha256": hashlib.sha256(read_text(slug, path).encode("utf-8")).hexdigest(),
            "plan_sha256": identity, "engine": "kokoro-onnx", "human_review_required": True}


def render_scene(slug: str, path: str, start: int, end: int) -> dict:
    plan = scene_plan(slug, path, start, end)
    model, voices = model_paths()
    if not status()["installed"]:
        raise ValueError("Install the optional local Kokoro ONNX model and voice bundle before rehearsing")
    import numpy as np
    import soundfile as sf

    with _LOCK:
        kokoro = _engine(str(model), str(voices))
        pieces = []
        for item in plan["segments"]:
            voice_id = item["voice_id"]
            lang = "en-gb" if voice_id.startswith(("bf_", "bm_")) else "en-us"
            samples, sample_rate = kokoro.create(
                item["text"].strip(), voice=voice_id, speed=item["speed"], lang=lang
            )
            if sample_rate != 24000 or len(samples) == 0:
                raise ValueError("Kokoro produced empty or unexpected-rate speech")
            shaped = apply_expression(samples, item.get("pitch_semitones", 0),
                                      item.get("gain_db", 0))
            pieces.append(np.asarray(shaped, dtype=np.float32))
            pieces.append(np.zeros(round(24 * item.get("pause_after_ms", 160)), dtype=np.float32))
        if not pieces:
            raise ValueError("No spoken scene material")
        if scene_plan(slug, path, start, end)["plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("Scene or voice assignments changed during rendering")
        final = np.concatenate(pieces[:-1])
        if final.size > 24000 * 180:
            raise ValueError("Rehearsal exceeds the three-minute limit")
        folder = _manifest_dir(slug)
        folder.mkdir(parents=True, exist_ok=True)
        identifier = uuid4().hex
        output = folder / (identifier + ".wav")
        staging = folder / (identifier + ".tmp.wav")
        sf.write(staging, final, 24000, subtype="PCM_16")
        staging.replace(output)
        record = {"id": identifier, "filename": output.name, "status": "unapproved_rehearsal",
                  "engine": "kokoro-onnx", "path": path, "start": start, "end": end,
                  "plan_sha256": plan["plan_sha256"], "source_sha256": plan["source_sha256"],
                  "segments": plan["segments"], "sample_rate": 24000,
                  "seconds": round(final.size / 24000, 3),
                  "audio_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                  "publication_approved": False}
        (folder / (identifier + ".json")).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return record


def rehearsal_file(slug: str, filename: str) -> Path:
    if not TAKE_NAME.fullmatch(filename):
        raise ValueError("Invalid local rehearsal filename")
    result = _manifest_dir(slug) / filename
    if not result.is_file():
        raise FileNotFoundError("Local rehearsal not found")
    return result
