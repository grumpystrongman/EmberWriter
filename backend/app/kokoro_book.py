"""Author-operated, crash-resumable neural book production.

A job advances exactly one short TTS chunk per explicit request. This allows
safe resume after a browser/server restart without pretending a rehearsal is
an approved or mastered commercial audiobook.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import wave
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import audio_production, kokoro_local
from .audiobook_local import _spoken_text
from .local_resources import reservation
from .publishing import compiled_documents
from .storage import project_root, read_text

MAX_CHAPTERS = 120
MAX_CHUNKS = 12000
CHUNK_CHARS = 300
_CHAPTER_FILE = re.compile(r"^chapter-[0-9]{3}-[0-9a-f]{10}\.wav$")


def _directory(slug: str) -> Path:
    return project_root(slug) / ".ember" / "kokoro-book"


def _jobfile(slug: str) -> Path:
    return _directory(slug) / "job.json"


def _atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    staging.replace(path)


def _read(slug: str) -> dict | None:
    path = _jobfile(slug)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("id") or not isinstance(data.get("chunks"), list):
        raise ValueError("Neural batch record is damaged; preserve files for recovery")
    return data


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _settings(slug: str) -> dict:
    state = audio_production.load(slug)
    return {"voices": state.get("kokoro_voices", {}),
            "casts": state.get("chapter_casts", {}),
            "pronunciations": state.get("pronunciations", [])}


def _split(text: str) -> list[str]:
    """Split narrator/actor turns without dropping or moving source characters."""
    if not text.strip():
        return []
    result = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + CHUNK_CHARS, len(text))
        if end < len(text):
            # Prefer sentence boundary; otherwise split on nearest whitespace.
            region = text[cursor:end]
            punctuation = list(re.finditer(r"""[.!?]["'”’)]?\s+""", region))
            if punctuation and punctuation[-1].end() >= CHUNK_CHARS // 2:
                end = cursor + punctuation[-1].end()
            else:
                boundary = max(region.rfind(" "), region.rfind("\n"))
                if boundary >= CHUNK_CHARS // 2:
                    end = cursor + boundary + 1
        if end <= cursor:
            raise ValueError("Cannot split audiobook text into safe narration segments")
        piece = text[cursor:end]
        if piece.strip():
            result.append(piece)
        cursor = end
    assert "".join(result) == text or not text.strip()
    return result


def _chapter_chunks(text: str, casts: list[dict], voices: dict, path: str,
                    pronunciations: list[dict] | None = None) -> list[dict]:
    cursor = 0
    turns = []
    for cast in sorted(casts, key=lambda item: item["start"]):
        start, end = cast["start"], cast["end"]
        if not (cursor <= start < end <= len(text)) or text[start:end] != cast["text"]:
            raise ValueError(f"{path}: manuscript dialogue assignment is stale or overlaps")
        if not cast.get("character"):
            raise ValueError(f"{path}: assign named characters to dialogue before neural production")
        if cursor < start:
            turns.append(("Narrator", text[cursor:start]))
        turns.append((cast["character"], text[start:end]))
        cursor = end
    if cursor < len(text):
        turns.append(("Narrator", text[cursor:]))
    result = []
    for speaker, passage in turns:
        if not passage.strip():
            continue
        profile = voices.get(speaker)
        if not profile or not profile.get("voice_id"):
            raise ValueError(f"{path}: assign a Kokoro voice to {speaker} before producing a book")
        # Pronunciation preferences are applied to the spoken rendering, never
        # written back to the author's manuscript.
        spoken = audio_production.spoken_replacements(passage, pronunciations or [])
        for part in _split(spoken):
            result.append({"speaker": speaker, "text": part,
                           "voice_id": profile["voice_id"], "speed": profile["speed"],
                           "status": "queued", "filename": "", "sha256": ""})
    return result


def start(slug: str) -> dict:
    existing = _read(slug)
    if existing and existing["status"] in ("queued", "running"):
        raise ValueError("An unfinished neural batch already exists; resume it rather than replace it")
    documents = compiled_documents(slug)
    if not 1 <= len(documents) <= MAX_CHAPTERS:
        raise ValueError("Select 1–120 Draft chapters before starting neural production")
    state = _settings(slug)
    model_status = kokoro_local.status()
    if not model_status["installed"]:
        raise ValueError("Install optional Kokoro model files before neural production")
    installed_voices = set(model_status.get("voice_ids", []))
    unavailable = sorted({profile["voice_id"] for profile in state["voices"].values()
                          if profile["voice_id"] not in installed_voices})
    if unavailable:
        raise ValueError("Kokoro voice styles are no longer installed: " + ", ".join(unavailable))
    chapters = []
    chunks = []
    for chapter in documents:
        path = chapter["path"]
        if not path.startswith("manuscript/") or not path.lower().endswith((".md", ".txt")):
            raise ValueError("Only manuscript chapters can be included in the neural book")
        raw = read_text(slug, path)
        text = _spoken_text(raw)
        if len(text.split()) < 5:
            raise ValueError(f"{path}: chapter is too short to narrate")
        selected = _chapter_chunks(text, state["casts"].get(path, []), state["voices"],
                                   path, state["pronunciations"])
        if not selected:
            raise ValueError(f"{path}: no spoken material")
        first = len(chunks)
        for item in selected:
            chunks.append({"chapter": len(chapters), **item})
        chapters.append({"path": path, "title": chapter["title"],
                         "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                         "first": first, "count": len(selected),
                         "filename": "", "status": "queued"})
        if len(chunks) > MAX_CHUNKS:
            raise ValueError("Novel exceeds maximum of 12,000 neural speech chunks")
    record = {"id": uuid4().hex, "status": "queued", "engine": "kokoro-onnx",
              "settings_sha256": _hash(state), "chapters": chapters, "chunks": chunks,
              "created_at": datetime.now(UTC).isoformat(), "human_review_required": True,
              "publication_approved": False, "message": "Ready for author-controlled generation"}
    _atomic_json(_jobfile(slug), record)
    return status(slug)


def status(slug: str) -> dict:
    record = _read(slug)
    if record is None:
        return {"exists": False, "status": "idle", "total": 0, "completed": 0}
    # Avoid shipping manuscript text in a polling response. Old draft audio
    # remains on disk after edits but must not be treated as a current take.
    stale_reason = ""
    try:
        _current(slug, record)
    except (FileNotFoundError, OSError, ValueError) as exc:
        stale_reason = str(exc)
    return {"exists": True, "id": record["id"], "status": record["status"],
            "stale": bool(stale_reason), "stale_reason": stale_reason,
            "total": len(record["chunks"]),
            "completed": sum(part["status"] == "rendered" for part in record["chunks"]),
            "chapters": [{"path": ch["path"], "title": ch["title"],
                          "status": ch["status"], "filename": ch["filename"]} for ch in record["chapters"]],
            "message": record["message"], "publication_approved": False}


def _current(slug: str, job: dict):
    if _hash(_settings(slug)) != job["settings_sha256"]:
        raise ValueError("Voice, dictionary, or casting settings changed. Start a new neural batch")
    for ch in job["chapters"]:
        if hashlib.sha256(read_text(slug, ch["path"]).encode("utf-8")).hexdigest() != ch["source_sha256"]:
            raise ValueError(f"{ch['path']}: manuscript changed. Start a new neural batch")


def _part_path(slug: str, job_id: str, index: int) -> Path:
    return _directory(slug) / job_id / f"part-{index:05d}.wav"


def _render_part(slug: str, job: dict, index: int):
    import numpy as np
    import soundfile as sf

    part = job["chunks"][index]
    model, voices = kokoro_local.model_paths()
    voice_id = part["voice_id"]
    lang = "en-gb" if voice_id.startswith(("bf_", "bm_")) else "en-us"
    # The author may rehearse a scene while a book is being produced.
    # Protect the shared in-process ONNX session from simultaneous use.
    with kokoro_local._LOCK:
        engine = kokoro_local._engine(str(model), str(voices))
        samples, frequency = engine.create(part["text"].strip(), voice=voice_id,
                                           speed=part["speed"], lang=lang)
    if frequency != 24000 or not 0 < len(samples) <= 24000 * 180:
        raise ValueError("Speech engine returned empty or invalid audio")
    dest = _part_path(slug, job["id"], index)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".tmp.wav")
    sf.write(temp, np.asarray(samples, dtype=np.float32), 24000, subtype="PCM_16")
    temp.replace(dest)
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def _assemble(slug: str, job: dict, chapter_index: int) -> str:
    ch = job["chapters"][chapter_index]
    indices = range(ch["first"], ch["first"] + ch["count"])
    if any(job["chunks"][i]["status"] != "rendered" for i in indices):
        raise ValueError("Cannot assemble a chapter before all neural chunks are rendered")
    name = f"chapter-{chapter_index + 1:03d}-{job['id'][:10]}.wav"
    target = _directory(slug) / job["id"] / name
    temp = target.with_suffix(".tmp.wav")
    with wave.open(str(temp), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        for i in indices:
            part = _part_path(slug, job["id"], i)
            if hashlib.sha256(part.read_bytes()).hexdigest() != job["chunks"][i]["sha256"]:
                raise ValueError("A produced audio chunk was changed or lost")
            with wave.open(str(part), "rb") as source:
                if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24000):
                    raise ValueError("Audio chunk has unexpected PCM format")
                while block := source.readframes(24000):
                    output.writeframesraw(block)
    temp.replace(target)
    return name


async def advance(slug: str) -> dict:
    """One bounded unit of work, safe after browser/server restarts."""
    async with reservation():
        job = _read(slug)
        if not job:
            raise ValueError("Start neural book production first")
        if job["status"] not in ("queued", "running", "paused"):
            raise ValueError("The neural batch is complete or blocked; start a new batch")
        _current(slug, job)
        if not kokoro_local.status()["installed"]:
            raise ValueError("Optional local Kokoro model files are unavailable")
        next_index = next((i for i, part in enumerate(job["chunks"])
                           if part["status"] != "rendered"), None)
        if next_index is None:
            job["status"] = "completed"
            job["message"] = "All draft chapters are rendered. Author review required."
            _atomic_json(_jobfile(slug), job)
            return status(slug)
        job["status"] = "running"
        job["message"] = f"Rendering neural segment {next_index + 1}/{len(job['chunks'])}"
        _atomic_json(_jobfile(slug), job)
        try:
            sha = await asyncio.to_thread(_render_part, slug, job, next_index)
            _current(slug, job)
            job["chunks"][next_index]["status"] = "rendered"
            job["chunks"][next_index]["sha256"] = sha
            job["chunks"][next_index]["filename"] = _part_path(
                slug, job["id"], next_index
            ).name
            ch_idx = job["chunks"][next_index]["chapter"]
            ch = job["chapters"][ch_idx]
            chapter_parts = job["chunks"][ch["first"]:ch["first"] + ch["count"]]
            if all(part["status"] == "rendered" for part in chapter_parts):
                ch["filename"] = await asyncio.to_thread(_assemble, slug, job, ch_idx)
                ch["status"] = "rendered_unapproved"
            if all(part["status"] == "rendered" for part in job["chunks"]):
                job["status"] = "completed"
                job["message"] = "Draft neural audiobook generated. Listen and approve each chapter."
            else:
                job["status"] = "queued"
                job["message"] = "Chunk saved. Continue when ready."
            _atomic_json(_jobfile(slug), job)
        except (OSError, ValueError, RuntimeError) as exc:
            job["status"] = "paused"
            job["message"] = f"Generation stopped: {exc}"
            _atomic_json(_jobfile(slug), job)
            raise
        return status(slug)


def chapter_audio(slug: str, filename: str) -> Path:
    job = _read(slug)
    if not job or not _CHAPTER_FILE.fullmatch(filename):
        raise ValueError("Invalid neural chapter filename")
    _current(slug, job)
    if filename not in {ch["filename"] for ch in job["chapters"] if ch["status"] == "rendered_unapproved"}:
        raise FileNotFoundError("Chapter draft recording is not available")
    result = _directory(slug) / job["id"] / filename
    if not result.is_file():
        raise FileNotFoundError("Chapter WAV is missing")
    return result
