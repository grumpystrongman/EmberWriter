"""Private, author-directed scene storyboards for a Series Vault.

These are planning artifacts, not canonical assertions. They deliberately never
edit manuscripts or approve any story evidence. Optimistic versions prevent one
open editor tab from silently overwriting another.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import series_canon as canon
from . import series_vault as vault

_LOCK = threading.RLock()
BEAT_KINDS = {"arrival", "spark", "obstacle", "reversal", "choice", "aftermath"}
MAX_BOARDS = 200
MAX_BEATS = 24


def _storage_path(series_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", series_id):
        raise ValueError("Invalid series ID")
    vault.series_detail(series_id)
    directory = vault._root() / "scene-boards"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{series_id}.json"


def _read(series_id: str) -> list[dict]:
    path = _storage_path(series_id)
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise TypeError("Scene storyboard storage is invalid")
    return value


def _write(series_id: str, boards: list[dict]) -> None:
    path = _storage_path(series_id)
    temp = path.with_name(f".{uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(boards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _validate(series_id: str, payload: dict) -> dict:
    volumes = vault.series_detail(series_id)["volumes"]
    book = payload.get("book")
    if type(book) is not int or book not in {v["ordinal"] for v in volumes}:
        raise ValueError("Select an existing book")
    sequence = payload.get("sequence", 0)
    if type(sequence) is not int or not 0 <= sequence <= 999999:
        raise ValueError("Scene position must be 0–999999")
    for field, maximum in (("title", 160), ("objective", 1200), ("conflict", 1200),
                           ("opening", 1600), ("aftermath", 1600), ("voice_notes", 1200)):
        value = payload.get(field, "")
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError(f"{field} must be text of at most {maximum} characters")
    if not payload.get("title", "").strip():
        raise ValueError("Storyboard needs a title")
    all_entities = {entity["id"]: entity for entity in canon.list_entities(series_id)}
    participants = payload.get("participants", [])
    if not isinstance(participants, list) or len(participants) > 20 or len(set(participants)) != len(participants):
        raise ValueError("Participants must be a list of up to 20 unique entities")
    if any(entity_id not in all_entities or all_entities[entity_id]["kind"] != "character"
           for entity_id in participants):
        raise ValueError("Participants must be characters from this series")
    pov = payload.get("pov_id") or None
    location = payload.get("location_id") or None
    if pov and (pov not in all_entities or all_entities[pov]["kind"] != "character"):
        raise ValueError("POV must be a character in this series")
    if location and (location not in all_entities or all_entities[location]["kind"] != "place"):
        raise ValueError("Location must be a place in this series")
    beats = payload.get("beats", [])
    if not isinstance(beats, list) or not 1 <= len(beats) <= MAX_BEATS:
        raise ValueError("A storyboard requires 1–24 beats")
    ids = []
    output_beats = []
    for beat in beats:
        if not isinstance(beat, dict) or not isinstance(beat.get("id"), str) or not re.fullmatch(
            r"[a-zA-Z0-9_-]{1,64}", beat["id"]):
            raise ValueError("Beat ID must be short and stable")
        ids.append(beat["id"])
        if beat.get("kind") not in BEAT_KINDS:
            raise ValueError("Unrecognized dramatic beat type")
        if (not isinstance(beat.get("title"), str) or not beat["title"].strip()
            or len(beat["title"]) > 120
            or not isinstance(beat.get("detail"), str) or len(beat["detail"]) > 1200
            or type(beat.get("pressure")) is not int or not 0 <= beat["pressure"] <= 100):
            raise ValueError("Invalid beat description or tension")
        output_beats.append({
            "id": beat["id"], "kind": beat["kind"],
            "title": beat["title"].strip(), "detail": beat["detail"].strip(),
            "pressure": beat["pressure"],
        })
    if len(ids) != len(set(ids)):
        raise ValueError("Beat IDs must be unique")
    return {
        "book": book, "sequence": sequence, "title": payload["title"].strip(),
        "objective": payload.get("objective", "").strip(),
        "conflict": payload.get("conflict", "").strip(),
        "opening": payload.get("opening", "").strip(),
        "aftermath": payload.get("aftermath", "").strip(),
        "voice_notes": payload.get("voice_notes", "").strip(),
        "pov_id": pov, "location_id": location, "participants": participants,
        "beats": output_beats,
    }


def list_boards(series_id: str, book: int | None = None) -> list[dict]:
    boards = _read(series_id)
    return sorted([board for board in boards if book is None or board["book"] == book],
                  key=lambda b: (b["book"], b["sequence"], b["created_at"]))


def create_board(series_id: str, payload: dict) -> dict:
    validated = _validate(series_id, payload)
    with _LOCK:
        boards = _read(series_id)
        if len(boards) >= MAX_BOARDS:
            raise ValueError("The series already has 200 scene boards")
        stamp = datetime.now(UTC).isoformat()
        result = {**validated, "id": uuid4().hex, "version": 1,
                  "created_at": stamp, "updated_at": stamp}
        boards.append(result)
        _write(series_id, boards)
    return result


def update_board(series_id: str, board_id: str, version: int, payload: dict) -> dict:
    validated = _validate(series_id, payload)
    with _LOCK:
        boards = _read(series_id)
        existing = next((b for b in boards if b["id"] == board_id), None)
        if not existing:
            raise FileNotFoundError("Scene board not found")
        if existing["version"] != version:
            raise ValueError("This scene changed in another view. Reload before saving.")
        updated = {**validated, "id": board_id, "version": version + 1,
                   "created_at": existing["created_at"],
                   "updated_at": datetime.now(UTC).isoformat()}
        boards[boards.index(existing)] = updated
        _write(series_id, boards)
        return updated


def delete_board(series_id: str, board_id: str, version: int) -> dict:
    with _LOCK:
        boards = _read(series_id)
        existing = next((b for b in boards if b["id"] == board_id), None)
        if not existing:
            raise FileNotFoundError("Scene board not found")
        if existing["version"] != version:
            raise ValueError("This scene changed in another view. Reload before deleting.")
        _write(series_id, [b for b in boards if b["id"] != board_id])
        return {"deleted": True, "id": board_id}
