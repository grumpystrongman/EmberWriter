from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .storage import project_root, read_text, save_text

IDEA_INBOX_PATH = "planning/idea-inbox.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _require_project(slug: str) -> None:
    if not (project_root(slug) / "project.json").exists():
        raise FileNotFoundError(slug)


def _load(slug: str) -> dict[str, Any]:
    _require_project(slug)
    try:
        raw = read_text(slug, IDEA_INBOX_PATH)
    except (FileNotFoundError, OSError, ValueError):
        return {"schema_version": 1, "ideas": []}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"schema_version": 1, "ideas": []}
    if not isinstance(payload, dict) or not isinstance(payload.get("ideas"), list):
        return {"schema_version": 1, "ideas": []}
    return payload


def _save(slug: str, payload: dict[str, Any]) -> None:
    save_text(slug, IDEA_INBOX_PATH, json.dumps(payload, indent=2, ensure_ascii=False))


def list_ideas(slug: str) -> list[dict[str, Any]]:
    ideas = _load(slug)["ideas"]
    return sorted(ideas, key=lambda item: str(item.get("created_at", "")), reverse=True)


def add_idea(
    slug: str,
    text: str,
    kind: str = "idea",
    source: str = "typed",
    destination: str = "inbox",
    context_path: str = "",
) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Idea text is required")
    payload = _load(slug)
    now = _now()
    idea = {
        "id": uuid4().hex,
        "text": cleaned,
        "kind": kind.strip() or "idea",
        "source": source.strip() or "typed",
        "destination": destination.strip() or "inbox",
        "context_path": context_path.strip(),
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    payload["ideas"].append(idea)
    _save(slug, payload)
    return idea


def update_idea(slug: str, idea_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    payload = _load(slug)
    for idea in payload["ideas"]:
        if idea.get("id") != idea_id:
            continue
        for key in ("text", "kind", "destination", "context_path", "status"):
            if key in patch and patch[key] is not None:
                value = str(patch[key]).strip()
                if key == "text" and not value:
                    raise ValueError("Idea text is required")
                idea[key] = value
        idea["updated_at"] = _now()
        _save(slug, payload)
        return idea
    raise FileNotFoundError(idea_id)


def delete_idea(slug: str, idea_id: str) -> None:
    payload = _load(slug)
    before = len(payload["ideas"])
    payload["ideas"] = [item for item in payload["ideas"] if item.get("id") != idea_id]
    if len(payload["ideas"]) == before:
        raise FileNotFoundError(idea_id)
    _save(slug, payload)
