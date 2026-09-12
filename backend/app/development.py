from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .development_models import DevelopmentState
from .storage import project_root, read_text, save_text, utc_now

DEVELOPMENT_PATH = "planning/story-development.json"


def empty_development_state() -> DevelopmentState:
    return DevelopmentState(updated_at=utc_now())


def load_development_state(slug: str) -> DevelopmentState:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    try:
        raw = read_text(slug, DEVELOPMENT_PATH)
    except FileNotFoundError:
        return empty_development_state()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Story development file contains invalid JSON") from exc
    return DevelopmentState.model_validate(payload)


def save_development_state(slug: str, state: DevelopmentState) -> DevelopmentState:
    normalized = state.model_copy(deep=True)
    normalized.updated_at = utc_now()
    save_text(
        slug,
        DEVELOPMENT_PATH,
        json.dumps(normalized.model_dump(), indent=2, ensure_ascii=False),
    )
    return normalized


def _ensure_ids(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for key, prefix in (("beats", "beat"), ("relationships", "rel"), ("threads", "thread")):
        values = normalized.get(key)
        if not isinstance(values, list):
            continue
        cleaned: list[Any] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            item = dict(value)
            if not str(item.get("id", "")).strip():
                item["id"] = f"{prefix}-{uuid4().hex[:12]}"
            cleaned.append(item)
        normalized[key] = cleaned
    return normalized


def validate_generated_state(payload: dict[str, Any]) -> DevelopmentState:
    return DevelopmentState.model_validate(_ensure_ids(payload))


def build_development_context(slug: str, *, max_items: int = 80) -> str:
    state = load_development_state(slug)
    if not (state.beats or state.character_arcs or state.relationships or state.threads):
        return ""

    lines = [
        "## Author-owned story development map",
        "This material is deliberately maintained by the author. Treat it as planning intent unless the manuscript establishes a later contradiction.",
    ]

    if state.beats:
        lines.append("### Planned plot beats")
        for beat in state.beats[:max_items]:
            placement = []
            if beat.act:
                placement.append(beat.act)
            if beat.chapter:
                placement.append(f"ch {beat.chapter}")
            if beat.scene:
                placement.append(f"scene {beat.scene}")
            where = f" ({', '.join(placement)})" if placement else ""
            lines.append(f"- [{beat.status}] {beat.title}{where}: {beat.summary or beat.purpose}")

    if state.character_arcs:
        lines.append("### Character arcs")
        for arc in state.character_arcs[:max_items]:
            parts = [
                f"want={arc.want}" if arc.want else "",
                f"need={arc.need}" if arc.need else "",
                f"midpoint={arc.midpoint_shift}" if arc.midpoint_shift else "",
                f"climax={arc.climax_choice}" if arc.climax_choice else "",
            ]
            lines.append(f"- {arc.character}: " + "; ".join(part for part in parts if part))

    if state.relationships:
        lines.append("### Author-tracked relationship state")
        for relationship in state.relationships[:max_items]:
            people = " / ".join(relationship.participants)
            metrics = (
                f"trust {relationship.trust}/5, closeness {relationship.closeness}/5, "
                f"conflict {relationship.conflict}/5"
            )
            status = relationship.status or relationship.label
            lines.append(f"- {people}: {status} ({metrics})")
            if relationship.boundaries:
                lines.append(f"  boundaries: {'; '.join(relationship.boundaries[:8])}")
            if relationship.unresolved_tension:
                lines.append(f"  unresolved: {'; '.join(relationship.unresolved_tension[:8])}")

    if state.threads:
        lines.append("### Setups, payoffs, and open story threads")
        for thread in state.threads[:max_items]:
            timing = []
            if thread.introduced_chapter:
                timing.append(f"introduced ch {thread.introduced_chapter}")
            if thread.target_payoff_chapter:
                timing.append(f"target payoff ch {thread.target_payoff_chapter}")
            suffix = f" ({', '.join(timing)})" if timing else ""
            lines.append(f"- [{thread.status}/{thread.kind}] {thread.title}{suffix}: {thread.setup}")
            if thread.payoff:
                lines.append(f"  payoff: {thread.payoff}")

    return "\n".join(lines)
