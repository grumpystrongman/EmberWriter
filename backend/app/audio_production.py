"""Project-local audiobook pronunciation, per-chapter narrator and proof notes.

Rules are *spoken replacements*, not IPA or SSML. The author's manuscript is
never modified; only the temporary TTS input is transformed. No cloud calls.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .storage import get_project, project_root

MAX_RULES = 150
MAX_PROFILES = 120
MAX_NOTES = 500
TERM = re.compile(r"^[\w][\w'’-]*(?:[ -][\w'’-]+){0,5}$", re.UNICODE)
_MUTATION_LOCKS: dict[str, threading.RLock] = {}


def synchronized(fn):
    @wraps(fn)
    def inner(slug: str, *args, **kwargs):
        with _MUTATION_LOCKS.setdefault(slug, threading.RLock()):
            return fn(slug, *args, **kwargs)
    return inner



def _file(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "audiobook-production.json"


def _empty() -> dict:
    return {"version": 1, "pronunciations": [], "chapter_profiles": {}, "proof_notes": []}


def load(slug: str) -> dict:
    path = _file(slug)
    if not path.is_file():
        return _empty()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("pronunciations"), list) or not isinstance(data.get("chapter_profiles"), dict) or not isinstance(data.get("proof_notes"), list):
        raise ValueError("Audiobook production settings are invalid")
    return data


def _write(slug: str, data: dict) -> dict:
    path = _file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return data


def _source(slug: str, path: str) -> None:
    from .audiobook_local import available_chapters
    if path not in {item["path"] for item in available_chapters(slug)}:
        raise FileNotFoundError("Select a manuscript chapter from this project")


def _validate_voice(voice: str) -> None:
    from .audiobook_local import VOICE_PATTERN, available_voices
    if voice and (not VOICE_PATTERN.fullmatch(voice) or voice not in available_voices()):
        raise ValueError("Choose an installed offline Windows voice")


@synchronized
def save_pronunciation(slug: str, written: str, spoken: str) -> dict:
    written, spoken = written.strip(), spoken.strip()
    if not 2 <= len(written) <= 90 or not TERM.fullmatch(written):
        raise ValueError("Written term must be a simple 2-90-character word or short phrase")
    if not 1 <= len(spoken) <= 140 or any(x in spoken for x in "<>\n\r"):
        raise ValueError("Spoken replacement must be plain words without SSML or markup")
    data = load(slug)
    key = written.casefold()
    duplicate = next((item for item in data["pronunciations"] if item["written"].casefold() == key), None)
    if duplicate:
        duplicate["spoken"] = spoken
    elif len(data["pronunciations"]) < MAX_RULES:
        data["pronunciations"].append({"written": written, "spoken": spoken})
    else:
        raise ValueError("Pronunciation dictionary is full")
    _write(slug, data)
    return data


@synchronized
def delete_pronunciation(slug: str, written: str) -> dict:
    data = load(slug)
    old = len(data["pronunciations"])
    data["pronunciations"] = [entry for entry in data["pronunciations"] if entry["written"].casefold() != written.casefold()]
    if len(data["pronunciations"]) == old:
        raise FileNotFoundError("Pronunciation term was not found")
    return _write(slug, data)


@synchronized
def save_profile(slug: str, path: str, voice: str, rate: int) -> dict:
    _source(slug, path)
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < -5 or rate > 5:
        raise ValueError("Narration rate must be between -5 and 5")
    _validate_voice(voice)
    data = load(slug)
    if path not in data["chapter_profiles"] and len(data["chapter_profiles"]) >= MAX_PROFILES:
        raise ValueError("Narration profile limit reached")
    data["chapter_profiles"][path] = {"voice": voice, "rate": rate}
    return _write(slug, data)


@synchronized
def delete_profile(slug: str, path: str) -> dict:
    data = load(slug)
    if path not in data["chapter_profiles"]:
        raise FileNotFoundError("Chapter narration profile was not found")
    del data["chapter_profiles"][path]
    return _write(slug, data)


def _signature(data: dict) -> str:
    # Order is semantically irrelevant. This fingerprint changes when an author
    # changes how a chapter is supposed to sound.
    payload = {"pronunciations": sorted(
        ((x["written"].casefold(), x["spoken"]) for x in data["pronunciations"]),
        key=lambda item: item[0]),
        "chapter_profiles": data["chapter_profiles"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def snapshot(slug: str) -> dict:
    data = load(slug)
    return {"pronunciations": list(data["pronunciations"]),
            "chapter_profiles": dict(data["chapter_profiles"]),
            "signature": _signature(data)}


def spoken_replacements(text: str, rules: list[dict]) -> str:
    if not rules:
        return text
    if len(rules) > MAX_RULES:
        raise ValueError("Too many narration substitutions")
    entries = []
    for item in rules:
        written, spoken = item["written"], item["spoken"]
        if not TERM.fullmatch(written) or not spoken or len(spoken) > 140 or any(x in spoken for x in "<>\n\r"):
            raise ValueError("Invalid narration dictionary rule")
        entries.append((written, spoken))
    # Longest phrase first; avoid replacing another rule's synthesized output.
    entries.sort(key=lambda item: -len(item[0]))
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w, _ in entries) + r")(?!\w)", re.I)
    replacements = {written.casefold(): spoken for written, spoken in entries}
    return pattern.sub(lambda match: replacements[match.group().casefold()], text)


@synchronized
def add_note(slug: str, path: str, seconds: float, note: str) -> dict:
    _source(slug, path)
    if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not 0 <= seconds <= 200000:
        raise ValueError("Proof-listening timestamp must be 0-200000 seconds")
    note = note.strip()
    if not 4 <= len(note) <= 1000:
        raise ValueError("Proof-listening note must be 4-1000 characters")
    data = load(slug)
    if len(data["proof_notes"]) >= MAX_NOTES:
        raise ValueError("Proof-listening ledger is full")
    # Track the currently rendered recording: future regenerated audio cannot
    # silently inherit completed proof notes for a different take.
    from .audiobook_local import list_renders
    render = next((entry for entry in list_renders(slug) if entry["source_path"] == path), None)
    if not render:
        raise ValueError("Narrate this chapter before adding a timed proof note")
    item = {"id": uuid4().hex, "path": path, "seconds": float(seconds),
            "note": note, "status": "open", "filename": render["filename"],
            "created_at": datetime.now(timezone.utc).isoformat()}
    data["proof_notes"].append(item)
    _write(slug, data)
    return item


@synchronized
def resolve_note(slug: str, note_id: str, resolved: bool) -> dict:
    data = load(slug)
    item = next((entry for entry in data["proof_notes"] if entry["id"] == note_id), None)
    if not item:
        raise FileNotFoundError("Proof-listening note not found")
    item["status"] = "resolved" if resolved else "open"
    _write(slug, data)
    return item
