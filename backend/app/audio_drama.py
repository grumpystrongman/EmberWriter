"""Author-directed local Fish Speech/Drama 3 proof takes.

Only explicit, source-anchored dialogue selections may be synthesized. The
configured endpoint is always loopback; no cloud service or voice uploads.
Neural takes are separate from the approved audiobook edition.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import wave
from pathlib import Path
from uuid import uuid4

import httpx
import msgpack

from . import audio_production
from .audiobook_local import _spoken_text
from .storage import project_root, read_text

REFERENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
TAKE_ID = re.compile(r"^[0-9a-f]{32}\.wav$")
MAX_AUDIO_BYTES = 40 * 1024 * 1024


def voice_library(slug: str) -> dict:
    return dict(audio_production.load(slug).get("neural_voices", {}))


@audio_production.synchronized
def save_voice(slug: str, character: str, reference_id: str, direction: str = "",
               seed: int | None = None) -> dict:
    """A reference ID is configured separately in the local Fish server."""
    character = character.strip()
    if not character or len(character) > 100 or any(ord(c) < 32 for c in character):
        raise ValueError("Enter a character name of 1-100 printable characters")
    if not REFERENCE_ID.fullmatch(reference_id):
        raise ValueError("Reference ID must be a local Fish voice ID")
    if len(direction) > 500 or any(c in direction for c in "<>"):
        raise ValueError("Performance direction must be 500 characters or fewer")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1):
        raise ValueError("Seed must be a nonnegative 32-bit integer")
    data = audio_production.load(slug)
    voices = data.setdefault("neural_voices", {})
    if character not in voices and len(voices) >= audio_production.MAX_CHARACTERS:
        raise ValueError("The neural voice library is full")
    voices[character] = {"reference_id": reference_id, "direction": direction.strip(), "seed": seed}
    audio_production._write(slug, data)
    return voices[character]


def _local_url(port: int) -> str:
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Choose a local speech server port between 1024 and 65535")
    return f"http://127.0.0.1:{port}"


def local_health(port: int = 8080) -> dict:
    """Health is a connectivity test; it does NOT prove which model is loaded."""
    try:
        response = httpx.get(_local_url(port) + "/v1/health", timeout=3)
        response.raise_for_status()
        return {"reachable": response.json().get("status") == "ok", "port": port,
                "model_verified": False}
    except (httpx.HTTPError, ValueError):
        return {"reachable": False, "port": port, "model_verified": False}


def _selected_dialogue(slug: str, path: str, start: int) -> tuple[dict, str]:
    data = audio_production.load(slug)
    span = next((row for row in data.get("chapter_casts", {}).get(path, [])
                 if row.get("start") == start and row.get("character")), None)
    if span is None:
        raise ValueError("Tag this exact dialogue span with a saved character first")
    text = _spoken_text(read_text(slug, path))
    if not (0 <= start < span["end"] <= len(text)) or text[start:span["end"]] != span["text"]:
        raise ValueError("Dialogue changed in the manuscript. Reassign the character before rendering")
    if len(span["text"].encode("utf-8")) > 2000:
        raise ValueError("Proof takes are limited to 2,000 UTF-8 bytes per dialogue selection")
    if span["character"] not in data.get("neural_voices", {}):
        raise ValueError("Save a neural voice reference for this character first")
    return span, text


def _folder(slug: str) -> Path:
    return project_root(slug) / ".ember" / "neural-proof-takes"


def render_take(slug: str, path: str, start: int, port: int = 8080) -> dict:
    """Generate one explicit local rehearsal take, never auto-approve or publish."""
    url = _local_url(port)
    span, text = _selected_dialogue(slug, path, start)
    setting = voice_library(slug)[span["character"]]
    # Fish's own /v1/tts protocol is MessagePack. A stored reference_id
    # selects voice timbre; seed alone does not make timbre reproducible.
    spoken = span["text"]
    if setting["direction"]:
        spoken = f"[{setting['direction']}] {spoken}"
    request = {"text": spoken, "references": [], "reference_id": setting["reference_id"],
               "format": "wav", "streaming": False}
    if setting.get("seed") is not None:
        request["seed"] = setting["seed"]
    payload = msgpack.packb(request, use_bin_type=True)
    with (
        httpx.Client(timeout=httpx.Timeout(120, connect=4), trust_env=False) as client,
        client.stream("POST", url + "/v1/tts", params={"format": "msgpack"},
                      content=payload, headers={"content-type": "application/msgpack"}) as response,
    ):
            response.raise_for_status()
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_AUDIO_BYTES:
                    raise ValueError("Local speech server response exceeds the 40 MB proof-take limit")
                chunks.append(chunk)
    audio = b"".join(chunks)
    if len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise ValueError("Local speech server did not return valid WAV audio")
    try:
        with wave.open(io.BytesIO(audio), "rb") as reader:
            if reader.getnframes() == 0 or reader.getframerate() < 16000 or reader.getnchannels() not in (1, 2):
                raise ValueError("Neural proof take has no audio or unsupported channel/sample rate")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Local speech server returned a malformed WAV file") from exc
    if _spoken_text(read_text(slug, path)) != text:
        raise ValueError("Source changed during synthesis; discard the generated take")
    identifier = uuid4().hex
    folder = _folder(slug)
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / (identifier + ".wav")
    staging = folder / (identifier + ".wav.tmp")
    staging.write_bytes(audio)
    staging.replace(output)
    record = {"id": identifier, "filename": output.name, "path": path,
              "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
              "text": span["text"], "start": start, "character": span["character"],
              "reference_id": setting["reference_id"], "direction": setting["direction"],
              "seed": setting.get("seed"), "audio_sha256": hashlib.sha256(audio).hexdigest(),
              "bytes": len(audio), "status": "unapproved_rehearsal"}
    (folder / (identifier + ".json")).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def take_file(slug: str, filename: str) -> Path:
    if not TAKE_ID.fullmatch(filename):
        raise ValueError("Invalid proof take filename")
    path = _folder(slug) / filename
    if not path.is_file():
        raise FileNotFoundError("Proof take was not found")
    return path

def production_plan(slug: str) -> dict:
    """Export an auditable, Binder-ordered script for human-reviewed drama work.

    Every actor line is tied to an exact manuscript span. Unassigned prose
    remains narrator material; we never guess dialogue speakers.
    """
    from .publishing import compiled_documents

    settings = audio_production.load(slug)
    voices = settings.get("neural_voices", {})
    casts = settings.get("chapter_casts", {})
    documents = compiled_documents(slug)
    if len(documents) > 120:
        raise ValueError("Drama production plan supports at most 120 Binder documents")
    chapters = []
    warnings = []
    for document in documents:
        path = document["path"]
        raw = read_text(slug, path)
        text = _spoken_text(raw)
        cursor = 0
        segments = []
        for cast in sorted(casts.get(path, []), key=lambda row: row["start"]):
            start, end = cast["start"], cast["end"]
            if not cursor <= start < end <= len(text) or text[start:end] != cast["text"]:
                warnings.append(f"{path}: casting selection is stale at offset {start}")
                continue
            if start > cursor:
                segments.append({"speaker": "Narrator", "start": cursor, "end": start,
                                 "text": text[cursor:start]})
            segments.append({"speaker": cast.get("character") or "Unassigned actor",
                             "start": start, "end": end, "text": text[start:end],
                             "manual_cast": True})
            cursor = end
        if cursor < len(text):
            segments.append({"speaker": "Narrator", "start": cursor, "end": len(text),
                             "text": text[cursor:]})
        for segment in segments:
            speaker = segment["speaker"]
            profile = voices.get(speaker, {})
            segment["reference_id"] = profile.get("reference_id")
            segment["direction"] = profile.get("direction", "")
            segment["seed"] = profile.get("seed")
            if not segment["reference_id"]:
                warnings.append(f"{path}: missing neural voice reference for {speaker}")
        chapters.append({"path": path, "title": document["title"],
                         "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                         "segments": segments})
    return {
        "schema_version": 1, "mode": "author_review_required",
        "chapters": chapters, "warnings": list(dict.fromkeys(warnings)),
        "voice_library": voices,
        "notice": "This is a direction/script export, not synthesized audio. "
                  "Narrator and every manually cast actor need a saved neural voice reference. "
                  "A human must review speaker attribution and licensing before rendering.",
    }
