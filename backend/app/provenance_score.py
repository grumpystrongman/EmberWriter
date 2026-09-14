from __future__ import annotations

from datetime import datetime
from typing import Any


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def later_revision_count(events: list[dict], by_path: dict[str, list[dict]]) -> int:
    total = 0
    for event in events:
        event_time = parse_time(event.get("created_at"))
        path = event.get("active_file")
        if not event_time or not path:
            continue
        for row in by_path.get(path, []):
            row_time = parse_time(row.get("created_at"))
            if row_time and row_time > event_time:
                total += 1
                break
    return total


def evidence_strength(
    documents: int,
    revisions: list[dict[str, Any]],
    events: list[dict[str, Any]],
    artifacts: dict[str, int | bool],
    later_revisions: int,
) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    if documents:
        score += 15
        reasons.append(f"{documents} current Draft document(s) are fingerprinted.")
    if revisions:
        score += min(25, len(revisions) * 2)
        reasons.append(f"{len(revisions)} recoverable document revision(s) provide creation history.")
    stamps = [stamp for stamp in (parse_time(row.get("created_at")) for row in revisions) if stamp]
    if len(stamps) >= 2:
        days = max(0, (max(stamps) - min(stamps)).days)
        score += 15 if days >= 30 else 10 if days >= 7 else 5 if days >= 1 else 0
        if days:
            reasons.append(f"Revision history spans {days} day(s).")
    if artifacts.get("voice_profile"):
        score += 10
        reasons.append("A learned author Voice Profile is present.")
    if artifacts.get("style_fidelity"):
        score += 10
        reasons.append("Measured Style Fidelity evidence is present.")
    story_files = sum(int(artifacts.get(key, 0) or 0) for key in (
        "characters", "world", "relationships", "timeline", "scenes", "research", "notes"
    ))
    if story_files >= 10:
        score += 15
    elif story_files >= 3:
        score += 8
    if story_files >= 3:
        reasons.append(f"{story_files} story-development artifact(s) support project lineage.")
    if events and later_revisions:
        score += 10
        reasons.append(f"{later_revisions} assistance event(s) are followed by later manuscript revisions.")
    score = min(100, score)
    label = "strong" if score >= 70 else "moderate" if score >= 40 else "limited"
    return {"score": score, "label": label, "reasons": reasons}
