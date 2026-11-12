"""Whole-source, deterministic evidence discovery for author review.

This is a conservative first-pass signal extractor, not semantic understanding.
It scans all rights-confirmed, immutable source snapshots, looking for literal
entity-linked statements with explicit predicates. No AI calls or canon writes.
All candidates carry exact source ranges and can be rejected individually.
"""
from __future__ import annotations

import re
from collections import Counter

from . import series_canon as canon
from . import series_vault as vault

# Require explicit, syntactically observable verbs. Do not infer personality,
# secret history, consent, deaths, psychology or other latent traits.
PATTERNS: tuple[tuple[str, str], ...] = (
    (r"trusts?", "trusts"),
    (r"distrusts?", "distrusts"),
    (r"fears?", "fears"),
    (r"protects?", "protects"),
    (r"betrays?", "betrays"),
    (r"loves?", "loves"),
    (r"hates?", "hates"),
    (r"wants?", "wants"),
    (r"seeks?", "seeks"),
    (r"guards?", "guards"),
    (r"carries?", "carries"),
    (r"holds?", "holds"),
    (r"hides?", "hides"),
    (r"knows?", "knows"),
    (r"believes?", "believes"),
    (r"discovers?", "discovers"),
    (r"reveals?", "reveals"),
    (r"promises?", "promises"),
    (r"forgives?", "forgives"),
    (r"resolves?", "resolves"),
    (r"foreshadows?", "foreshadows"),
    (r"awakens?", "awakens"),
    (r"destroys?", "destroys"),
    (r"finds?", "finds"),
    (r"moves?", "moves"),
)
_VERBS = "|".join(f"(?P<verb{i}>{pattern})" for i, (pattern, _) in enumerate(PATTERNS))
_SENTENCE = re.compile(r"[^.!?\n]{2,}[.!?]|[^.!?\n]{2,}$", re.MULTILINE)
MAX_SCAN_CHARS = 4_000_000
MAX_CANDIDATES = 1200
MAX_MATCHES_PER_ENTITY = 80


def discover(series_id: str, *, book: int | None = None,
             limit: int = 120, offset: int = 0) -> dict:
    if not 1 <= limit <= 250 or offset < 0:
        raise ValueError("Choose 1–250 discoveries and a nonnegative offset")
    series = vault.series_detail(series_id)
    volumes = [v for v in series["volumes"]
               if book is None or v["ordinal"] == book]
    if book is not None and not volumes:
        raise ValueError("Book not in this series")
    entities = canon.list_entities(series_id)
    known = canon.list_facts(series_id)
    known_quotes = {(f["source_id"], f["quote_start"], f["predicate"],
                     f["subject_id"]) for f in known}
    names: dict[str, dict | None] = {}
    for entity in entities:
        for alias in [entity["name"], *entity["aliases"]]:
            key = alias.casefold()
            if key in names and names[key] is not entity:
                names[key] = None  # ambiguous alias: do not use
            else:
                names[key] = entity
    # A single anchored regex avoids one regex call per character per sentence.
    distinct = sorted((key for key, entity in names.items()
                       if entity and len(key) >= 3), key=len, reverse=True)
    subject_re = (re.compile(r"(" + "|".join(map(re.escape, distinct)) + r")(?!\w)",
                             re.IGNORECASE) if distinct else None)
    results = []
    scanned_sources = 0
    skipped_sources = 0
    truncated = False
    per_entity: Counter[str] = Counter()
    for volume in volumes:
        for src in volume["sources"]:
            _, text = vault.source_text(series_id, src["id"])
            scanned_sources += 1
            if len(text) > MAX_SCAN_CHARS:
                skipped_sources += 1
                text = text[:MAX_SCAN_CHARS]
            for sentence in _SENTENCE.finditer(text):
                phrase = sentence.group().strip()
                if not 14 <= len(phrase) <= 450:
                    continue
                # Require a name at the beginning of an affirmative sentence.
                # This rejects dialogue quotes, negations, unclear pronouns and
                # most narration that cannot support a literal subject claim.
                name_match = subject_re.match(phrase) if subject_re else None
                if not name_match:
                    continue
                entity = names.get(name_match.group(1).casefold())
                if entity is None or per_entity[entity["id"]] >= MAX_MATCHES_PER_ENTITY:
                    continue
                remainder = phrase[name_match.end():]
                match = re.match(r"\s+(" + _VERBS + r")\s+(?P<value>.+?)[.!?]?$",
                                 remainder, re.IGNORECASE)
                if not match:
                    continue
                predicate = next(label for i, (_,label) in enumerate(PATTERNS)
                                 if match.group(f"verb{i}") is not None)
                value = match.group("value").strip(" .!?\t\r\n")
                if not 2 <= len(value) <= 200:
                    continue
                if value.casefold().startswith(("not ", "never ", "no ")):
                    continue
                quote_start = sentence.start() + (len(sentence.group()) - len(sentence.group().lstrip()))
                quote_end = sentence.end() - (len(sentence.group()) - len(sentence.group().rstrip()))
                quote = text[quote_start:quote_end]
                if not quote or len(quote) > 450:
                    continue
                if (src["id"], quote_start, predicate, entity["id"]) in known_quotes:
                    continue
                target = next((e for e in entities if e["id"] != entity["id"]
                               and value.casefold() == e["name"].casefold()), None)
                results.append({
                    "subject_id": entity["id"], "subject_name": entity["name"],
                    "predicate": predicate, "object_text": value,
                    "object_entity_id": target["id"] if target else None,
                    "scope": "world", "knower_id": None,
                    "start_book": volume["ordinal"], "start_sequence": src["sequence"],
                    "source_id": src["id"], "source_title": src["title"],
                    "source_path": src["source_path"], "quote_start": quote_start,
                    "quote_end": quote_end, "quote": quote,
                    "confidence": "literal-pattern", "status": "unsaved_review_candidate",
                })
                per_entity[entity["id"]] += 1
                if len(results) >= MAX_CANDIDATES:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
    results.sort(key=lambda f: (f["start_book"], f["source_path"], f["quote_start"]))
    return {
        "series_id": series_id, "candidates": results[offset:offset + limit],
        "total": len(results), "offset": offset, "limit": limit,
        "scanned_sources": scanned_sources, "skipped_large_sources": skipped_sources,
        "truncated": truncated, "saved": False,
        "mode": "deterministic_literal_review",
        "caveat": "Literal language candidates may be figurative, negated outside the sentence, or otherwise not canon. Verify the quotation and approve deliberately.",
    }
