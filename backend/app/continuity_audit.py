"""Conservative offline cross-chapter narrative continuity candidate detection.

No claims of infallible semantic inference: a character moving, changing
alliances, or learning new facts is not by itself a contradiction. Every
candidate cites two previously extracted, provenance-bound source facts.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from .memory import list_memory
from .memory_integrity import reconcile_story_memory

STATIC = {
    "birthplace": {"birthplace", "born in", "born at", "place of birth", "birth location"},
    "birth_date": {"born on", "date of birth", "birthday", "birth date"},
    "species": {"species", "race", "kind of being"},
    "father": {"father"},
    "mother": {"mother"},
    "parent": {"parent"},
    "eye_color": {"eye color", "eyes are", "eye colour"},
    "hair_color": {"natural hair color", "hair colour", "hair color"},
    "origin": {"origin", "homeworld", "planet of origin"},
    "event_date": {"date", "happened on", "occurred on", "occurred at", "takes place on"},
}
KNOWS = {"knows", "learned", "is aware of", "discovered", "understands"}
DOES_NOT_KNOW = {"does not know", "doesn't know", "is unaware of", "has not learned", "ignorant of"}


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'-]", " ", str(value).casefold())).strip()


def _predicate(value: str) -> str:
    key = _norm(value)
    for canonical, aliases in STATIC.items():
        if key in aliases:
            return canonical
    return key


def _date(value: str) -> str | None:
    v = re.sub(r"\s+", " ", value.strip().replace(",", ""))
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d %Y", "%b %d %Y",
                "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _facts(fact: dict) -> dict:
    return {
        "kind": fact["kind"], "subject": fact["subject"],
        "predicate": fact["predicate"], "object": fact["object"],
        "source_path": fact["source_path"],
        "chapter_order": fact.get("chapter_order", 0),
        "confidence": fact.get("confidence", 1.0),
    }


def find_conflicts(facts: list[dict]) -> list[dict]:
    """Only report review candidates, never silently rewrite manuscripts."""
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for fact in facts:
        if fact.get("confidence", 0) < 0.75:
            continue
        kind = fact.get("kind")
        if kind not in {"canon", "character_state", "character_knowledge",
                        "relationship", "timeline", "location", "object", "ability"}:
            continue
        subject = _norm(fact.get("subject", ""))
        pred = _predicate(fact.get("predicate", ""))
        obj = _norm(fact.get("object", ""))
        if not subject or not pred or not obj:
            continue
        by_key[(kind, subject, pred)].append(fact)
    candidates = []
    seen = set()
    for (kind, subject, pred), rows in by_key.items():
        rows.sort(key=lambda x: (x.get("chapter_order", 0), x["source_path"]))
        for index, left in enumerate(rows):
            for right in rows[index+1:]:
                if left["source_path"] == right["source_path"]:
                    continue
                old, new = _norm(left["object"]), _norm(right["object"])
                if old == new:
                    continue
                if pred in {"event_date", "birth_date"}:
                    old_date, new_date = _date(left["object"]), _date(right["object"])
                    if old_date and new_date and old_date == new_date:
                        continue
                    if not (old_date and new_date):
                        continue  # non-dates are not reliable timestamp conflicts
                    category = "date_conflict"
                elif pred in STATIC and kind != "character_state":
                    category = "static_fact_conflict"
                elif kind == "relationship" and left.get("chapter_order") == right.get("chapter_order"):
                    category = "relationship_state_review"
                elif kind == "canon":
                    category = "world_rule_review"
                else:
                    continue  # dynamic states can legitimately change
                identity = (category, tuple(sorted((left["source_path"], right["source_path"]))),
                            subject, pred)
                if identity in seen:
                    continue
                seen.add(identity)
                candidates.append({
                    "type": category, "severity": "review",
                    "subject": left["subject"], "predicate": pred,
                    "earlier": _facts(left), "later": _facts(right),
                    "detail": "Review these two source facts; a retcon, time jump, or intentional change may explain the difference.",
                })
                if len(candidates) >= 500:
                    return candidates
    knowledge: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for fact in facts:
        if fact.get("kind") != "character_knowledge" or fact.get("confidence", 0) < 0.75:
            continue
        pred = _norm(fact.get("predicate", ""))
        if pred in KNOWS or pred in DOES_NOT_KNOW:
            knowledge[(_norm(fact["subject"]), _norm(fact["object"]))].append(fact)
    for rows in knowledge.values():
        rows.sort(key=lambda x: (x.get("chapter_order", 0), x["source_path"]))
        prior_known = None
        for fact in rows:
            pred = _norm(fact["predicate"])
            if pred in KNOWS:
                prior_known = fact
            elif pred in DOES_NOT_KNOW and prior_known is not None:
                if prior_known["source_path"] != fact["source_path"]:
                    candidates.append({
                        "type": "knowledge_reversal_review", "severity": "review",
                        "subject": fact["subject"], "predicate": "character_knowledge",
                        "earlier": _facts(prior_known), "later": _facts(fact),
                        "detail": "Character previously knew this; confirm forgetting, deception, or an intentional timeline change.",
                    })
                    if len(candidates) >= 500:
                        break
    return candidates


def audit(slug: str) -> dict[str, Any]:
    reconciliation = reconcile_story_memory(slug)
    facts = list_memory(slug, limit=5000)
    candidates = find_conflicts(facts)
    return {
        "status": "review_required" if candidates else "no_candidates",
        "candidates": candidates, "fact_count": len(facts),
        "stale_analyses_removed": len(reconciliation["stale_paths"]),
        "coverage": "Analyzed manuscript memory only; unanalysed chapters are not checked.",
        "disclaimer": "Conservative source-anchored contradiction candidates, not complete semantic or timeline certification. Human review is required.",
    }
