"""Literal, quote-anchored event/scene leads; never asserts fictional truth.

The scanner uses explicit time-change language and established entity names,
not a model-generated chronology. Leads are navigation/review proposals only.
"""
from __future__ import annotations

import re

from . import series_canon as canon
from . import series_epub_index as index
from . import series_vault as vault

CUES = (
    ("before", re.compile(r"\bbefore\b", re.IGNORECASE)),
    ("after", re.compile(r"\bafter\b", re.IGNORECASE)),
    ("later", re.compile(r"\blater\b", re.IGNORECASE)),
    ("earlier", re.compile(r"\bearlier\b", re.IGNORECASE)),
    ("meanwhile", re.compile(r"\bmeanwhile\b", re.IGNORECASE)),
    ("then", re.compile(r"\bthen\b", re.IGNORECASE)),
    ("next_day", re.compile(r"\bthe next day\b", re.IGNORECASE)),
    ("years_later", re.compile(r"\byears later\b", re.IGNORECASE)),
    ("flashback", re.compile(r"\bflashback\b", re.IGNORECASE)),
    ("remembered", re.compile(r"\bremembered\b", re.IGNORECASE)),
    ("learned", re.compile(r"\b(?:learned|realized|discovered)\b", re.IGNORECASE)),
    ("revealed", re.compile(r"\b(?:revealed|confessed|told)\b", re.IGNORECASE)),
    ("changed", re.compile(r"\b(?:became|changed|transformed|died|returned|left)\b", re.IGNORECASE)),
)
SENTENCE = re.compile(r"[^.!?\n]{20,400}(?:[.!?]|(?=\n|$))")
MAX_PER_SOURCE = 30
MAX_PER_QUERY = 800


def _names(entities: list[dict]) -> list[tuple[str, re.Pattern]]:
    names = {}
    for entity in entities:
        if entity["kind"] not in ("character", "place", "artifact", "faction", "event"):
            continue
        for value in [entity["name"], *entity.get("aliases", [])]:
            if 2 <= len(value.strip()) <= 80:
                names.setdefault(value.casefold(), (entity["name"], value))
    return [
        (name, re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE))
        for name, alias in names.values()
    ]


def scan(series_id: str, *, book: int | None = None, limit: int = 80,
         offset: int = 0) -> dict:
    if not 1 <= limit <= 250 or offset < 0:
        raise ValueError("Use a valid event lead page size and offset")
    detail = vault.series_detail(series_id)
    entities = _names(canon.list_entities(series_id))
    leads = []
    scanned = 0
    per_source_limit = MAX_PER_SOURCE if book is not None else 8
    for volume in detail["volumes"]:
        if book is not None and volume["ordinal"] != book:
            continue
        for source in volume["sources"]:
            record, content = vault.source_text(series_id, source["id"])
            scanned += 1
            saved = index.read(series_id, source["id"])
            sections = sorted(saved["sections"], key=lambda r: r["start"]) if saved else []
            added = 0
            for match in SENTENCE.finditer(content):
                if added >= per_source_limit or len(leads) >= MAX_PER_QUERY:
                    break
                quote = match.group().strip()
                start = match.start() + len(match.group()) - len(match.group().lstrip())
                if len(quote) < 30 or not any(char.isalpha() for char in quote):
                    continue
                cues = [label for label, pattern in CUES if pattern.search(quote)]
                if not cues:
                    continue
                involved = [name for name, pattern in entities if pattern.search(quote)]
                if not involved:
                    continue
                in_sections = [section for section in sections
                               if section["start"] <= start < section["end"]]
                anchored = min(in_sections, key=lambda r: r["end"] - r["start"],
                               default=None)
                leads.append({
                    "source_id": source["id"], "source_hash": record["sha256"],
                    "book": volume["ordinal"], "source_title": source["title"],
                    "quote": quote, "quote_start": start, "quote_end": start + len(quote),
                    "entities_mentioned": involved[:12], "literal_cues": cues,
                    "section_label": anchored["title"] if anchored else None,
                    "section_index": anchored["index"] if anchored else None,
                    "status": "unreviewed_event_lead",
                    "event_claimed": False, "chronology_inferred": False,
                    "narrator_reliability_checked": False, "canon_approved": False,
                })
                added += 1
            if len(leads) >= MAX_PER_QUERY:
                break
        if len(leads) >= MAX_PER_QUERY:
            break
    return {
        "series_id": series_id, "book": book,
        "scanned_sources": scanned, "total": len(leads),
        "leads": leads[offset:offset+limit], "offset": offset,
        "truncated": len(leads) >= MAX_PER_QUERY,
        "source_text_returned": "exact_quoted_passages_only",
        "canon_approved": False,
        "caveat": (
            "Literal temporal and narrative verbs are review leads, not verified "
            "events. Flashbacks, metaphor, unreliable narrators, POV and world "
            "versus character knowledge remain unclassified until author review."
        ),
    }
