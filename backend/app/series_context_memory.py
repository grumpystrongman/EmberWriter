"""Author-reviewable contextual candidate memory, separate from approved story canon.

A candidate card is an interpretation from local source passages. Only an explicit
review action changes its research status. This never writes series-canon assertions.
"""
from __future__ import annotations

import json
import os
import re
import threading
from collections import deque
from pathlib import Path
from uuid import uuid4

from . import series_vault as vault

_REVIEW_LOCK = threading.Lock()
_ID = re.compile(r"[0-9a-f]{32}")
_CARD_ID = re.compile(r"[0-9a-f]{64}")
VALID_DECISIONS = {"confirmed_for_research", "rejected"}


def _paths(series_id: str) -> tuple[Path, Path]:
    if not _ID.fullmatch(series_id):
        raise ValueError("Invalid series ID")
    vault.series_detail(series_id)
    root = vault._root()
    return (root / f"context-proposals-{series_id}.jsonl",
            root / f"context-proposal-reviews-{series_id}.json")


def _decisions(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {k: v for k, v in doc.items() if _CARD_ID.fullmatch(k)
            and v in VALID_DECISIONS}


def list_candidates(series_id: str, *, max_book: int = 9999,
                    limit: int = 30) -> dict:
    if not 1 <= max_book <= 9999 or not 1 <= limit <= 100:
        raise ValueError("Invalid review range")
    cards_path, reviews_path = _paths(series_id)
    if not cards_path.is_file():
        return {"items": [], "auto_canon_approved": False}
    reviews = _decisions(reviews_path)
    with cards_path.open("r", encoding="utf-8") as fp:
        recent_lines = deque(fp, maxlen=max(100, limit * 5))
    items = []
    seen = set()
    for line in reversed(recent_lines):
        try:
            card = json.loads(line)
        except ValueError:
            continue
        if (not isinstance(card, dict)
                or not _CARD_ID.fullmatch(str(card.get("id", "")))
                or card["id"] in seen
                or type(card.get("as_of_book")) is not int
                or card["as_of_book"] > max_book
                or card["as_of_book"] < 1):
            continue
        seen.add(card["id"])
        items.append({
            "id": card["id"], "question": str(card.get("question", ""))[:1500],
            "interpretation": str(card.get("interpretation", ""))[:3000],
            "facet": str(card.get("facet", "unknown"))[:60],
            "as_of_book": card["as_of_book"],
            "citations": card.get("citations", [])[:8],
            "review_state": reviews.get(card["id"], "pending_author_review"),
            "semantic_entailment": "unverified",
            "auto_canon_approved": False,
        })
        if len(items) >= limit:
            break
    return {"items": items, "auto_canon_approved": False,
            "description": "Unverified candidate knowledge and explicitly reviewed research notes; "
                           "never automatically approved canon."}


def review(series_id: str, card_id: str, decision: str) -> dict:
    if not _CARD_ID.fullmatch(card_id) or decision not in VALID_DECISIONS:
        raise ValueError("Choose a valid proposal and review decision")
    cards_path, reviews_path = _paths(series_id)
    if not cards_path.is_file():
        raise FileNotFoundError("Proposal not found")
    with _REVIEW_LOCK:
        row = next((c for c in list_candidates(series_id, limit=100)["items"]
                    if c["id"] == card_id), None)
        if row is None:
            raise FileNotFoundError("Proposal not in recent research records")
        # Do not allow approval of hallucinated/no-longer-existing source offsets.
        if decision == "confirmed_for_research":
            if not isinstance(row["citations"], list) or not row["citations"]:
                raise ValueError("Research interpretation requires manuscript citations")
            for source in row["citations"]:
                if not isinstance(source, dict):
                    raise TypeError("Malformed source")
                src_id = source.get("source_id")
                start, end = source.get("start"), source.get("end")
                if (not isinstance(src_id, str)
                        or type(start) is not int or type(end) is not int
                        or not 0 <= start < end):
                    raise ValueError("Malformed source coordinates")
                _, text = vault.source_text(series_id, src_id)
                if end > len(text):
                    raise ValueError("Source no longer matches stored coordinates")
        reviews = _decisions(reviews_path)
        reviews[card_id] = decision
        temp = reviews_path.with_name(f".{reviews_path.name}.{uuid4().hex}.tmp")
        try:
            temp.write_text(json.dumps(reviews, indent=2), encoding="utf-8")
            os.replace(temp, reviews_path)
        finally:
            temp.unlink(missing_ok=True)
    return {"id": card_id, "review_state": decision,
            "auto_canon_approved": False, "independent_expert_review": False}


def approved_research_context(series_id: str, question: str, *, as_of_book: int,
                              limit: int = 2) -> list[dict]:
    """Use explicit human-confirmed context as an annotated hypothesis, never proof."""
    items = list_candidates(series_id, max_book=as_of_book, limit=100)["items"]
    qwords = {x.casefold() for x in re.findall(r"[^\W_]{4,}", question)}
    ranked = []
    for row in items:
        if row["review_state"] != "confirmed_for_research":
            continue
        prior_words = {x.casefold() for x in
                       re.findall(r"[^\W_]{4,}", row["question"])}
        overlap = len(qwords & prior_words)
        if overlap:
            ranked.append((overlap, row))
    ranked.sort(key=lambda item: -item[0])
    return [{
        "claim": row["interpretation"], "book_cutoff": row["as_of_book"],
        "source_refs": row["citations"], "status": "author_confirmed_for_research_not_canon",
    } for _, row in ranked[:limit]]
