"""Source-exact dialogue attribution *clues* only, not verified speakers or POV.

The EPUB import preserves dialogue quotation marks, but not all structure
survives. This scanner only proposes a candidate when a quote and an explicit
named speech-verb cue are close enough to inspect. Named speakers, narrators,
perspective or truthfulness are never inferred or approved.
"""
from __future__ import annotations

import re
from collections import Counter

from . import series_canon as canon
from . import series_epub_index as epub_index
from . import series_vault as vault

QUOTED = re.compile(r'(?P<open>["“])(?P<text>[^"”\n]{8,340})(?P<close>["”])')
SPEECH = r"(?:said|asked|replied|whispered|shouted|muttered|answered|cried|yelled|told|snapped)"
MAX_SOURCE_MATCHES = 18000
MAX_LEADS = 500
MAX_CONTEXT = 160


def _names(entity: dict) -> list[str]:
    return sorted({value.strip() for value in [entity["name"], *entity["aliases"]]
                   if 2 <= len(value.strip()) <= 120}, key=len, reverse=True)


def _cue(left: str, right: str, names: list[str]) -> list[tuple[str, str]]:
    cues = []
    for name in names:
        escaped = re.escape(name)
        before = (
            rf"(?<!\w){escaped}(?!\w)\s+(?:\w+\s+){{0,2}}{SPEECH}\b",
            rf"\b{SPEECH}\s+(?:\w+\s+){{0,2}}(?<!\w){escaped}(?!\w)",
        )
        after = (
            rf"\b{SPEECH}\s+(?:\w+\s+){{0,2}}(?<!\w){escaped}(?!\w)",
            rf"(?<!\w){escaped}(?!\w)\s+(?:\w+\s+){{0,2}}{SPEECH}\b",
        )
        if any(re.search(pattern+r"[\s,:;—-]*$", left, re.IGNORECASE) for pattern in before):
            cues.append(("before_quote", name))
        if any(re.match(r"^[,;.!?\s-]{0,12}"+pattern, right, re.IGNORECASE)
               for pattern in after):
            cues.append(("after_quote", name))
    return cues


def scan(series_id: str, *, book: int, entity_id: str | None = None,
         limit: int = 60, offset: int = 0) -> dict:
    if not 1 <= book <= 9999 or not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid dialogue evidence scan bounds")
    series = vault.series_detail(series_id)
    selected_volumes = [volume for volume in series["volumes"] if volume["ordinal"] == book]
    if not selected_volumes:
        return {"series_id": series_id, "book": book, "leads": [],
                "total": 0, "scanned_sources": 0, "ambiguous_cues": 0,
                "auto_speaker_approved": False}
    entities = [entity for entity in canon.list_entities(series_id)
                if entity["kind"] == "character"]
    if entity_id and not any(entity["id"] == entity_id for entity in entities):
        raise FileNotFoundError("Character not found in this series")
    labels = [(entity, _names(entity)) for entity in entities]
    proposals = []
    checked = 0
    ambiguity = Counter()
    for source in selected_volumes[0]["sources"]:
        original, content = vault.source_text(series_id, source["id"])
        structure = epub_index.read(series_id, source["id"])
        for quote in QUOTED.finditer(content):
            checked += 1
            if checked > MAX_SOURCE_MATCHES or len(proposals) >= MAX_LEADS:
                break
            start, end = quote.span()
            left = content[max(0, start-95):start]
            right = content[end:min(len(content), end+95)]
            hints = []
            for entity, names in labels:
                for position, matched_name in _cue(left, right, names):
                    hints.append((entity, position, matched_name))
            if not hints:
                continue
            available = {item[0]["id"] for item in hints}
            if entity_id and entity_id not in available:
                continue
            is_ambiguous = len(available) != 1
            if is_ambiguous:
                ambiguity["multiple_character_cues"] += 1
            context_start = max(0, start-MAX_CONTEXT)
            context_end = min(len(content), end+MAX_CONTEXT)
            section = next((piece for piece in (structure or {}).get("sections", [])
                            if piece["start"] <= start < piece["end"]), None)
            proposals.append({
                "source_id": source["id"], "source_hash": original["sha256"],
                "book": book, "quote_start": start, "quote_end": end,
                "quote": content[start:end],
                "context_start": context_start, "context_end": context_end,
                "context": content[context_start:context_end],
                "speaker_hints": [{
                    "entity_id": entity["id"], "name": entity["name"],
                    "position": position, "matched_name": name,
                } for entity, position, name in hints],
                "unique_candidate_speaker": next(iter(available)) if not is_ambiguous else None,
                "ambiguous_speaker": is_ambiguous,
                "pov_inferred": False, "speaker_verified": False,
                "section_title": section["title"] if section else None,
                "review_status": "candidate_not_approved",
            })
        if checked > MAX_SOURCE_MATCHES or len(proposals) >= MAX_LEADS:
            break
    return {
        "series_id": series_id, "book": book, "entity_id": entity_id,
        "total": len(proposals), "leads": proposals[offset:offset+limit],
        "scanned_sources": len(selected_volumes[0]["sources"]),
        "ambiguous_cues": ambiguity["multiple_character_cues"],
        "truncated": checked > MAX_SOURCE_MATCHES or len(proposals) >= MAX_LEADS,
        "auto_speaker_approved": False, "auto_pov_inferred": False,
        "disclaimer": (
            "Quoted strings with nearby named speech verbs are review clues only. "
            "Adjacent narration, irony, nested quotes, aliases, scene boundaries, "
            "and unreliable speakers can mislead. No POV, speaker identity, "
            "character knowledge or approved canon is inferred."
        ),
    }
