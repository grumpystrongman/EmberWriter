"""Source-exact character presence atlas with no inferred relationships or motives.

Recompute directly from immutable imported snapshots. Entity labels and aliases
are author-maintained. A textual mention is NOT proof of presence in a scene,
speaker identity, actual meeting, or character knowledge.
"""
from __future__ import annotations

import re
from collections import Counter

from . import series_canon as canon
from . import series_epub_index as indexes
from . import series_vault as vault

MAX_BOOKS = 150
MAX_SAMPLE_PER_BOOK = 4
MAX_ENTITY_ALIASES = 31
CONTEXT_LEFT = 90
CONTEXT_RIGHT = 160
MAX_TOTAL_SAMPLES = 1500


def _forms(entity: dict) -> list[re.Pattern]:
    options = [entity["name"], *entity.get("aliases", [])][:MAX_ENTITY_ALIASES]
    unique = sorted({text.strip().casefold(): text.strip() for text in options
                     if 2 <= len(text.strip()) <= 120}.values(), key=len, reverse=True)
    return [
        re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
        for name in unique
    ]


def _intervals(content: str, forms: list[re.Pattern]):
    points = []
    for expression in forms:
        points.extend((match.start(), match.end()) for match in expression.finditer(content))
    points.sort()
    compact = []
    for start, end in points:
        if compact and start < compact[-1][1]:
            if end > compact[-1][1]:
                compact[-1] = (compact[-1][0], end)
            continue
        compact.append((start, end))
    return compact


def _context(content: str, start: int, end: int) -> tuple[int, int, str]:
    left = max(0, start - CONTEXT_LEFT)
    right = min(len(content), end + CONTEXT_RIGHT)
    # Do not imply that a clipped fragment is a complete sentence.
    return left, right, content[left:right]


def _section(saved: dict | None, pos: int) -> dict | None:
    sections = (saved or {}).get("sections", [])
    eligible = [row for row in sections if row["start"] <= pos < row["end"]]
    return min(eligible, key=lambda row: row["end"] - row["start"], default=None)


def atlas(series_id: str, *, entity_id: str, min_book: int = 1,
          max_book: int = 9999, limit_per_book: int = MAX_SAMPLE_PER_BOOK) -> dict:
    if not 1 <= min_book <= max_book <= 9999:
        raise ValueError("Invalid book range")
    if not 1 <= limit_per_book <= 10:
        raise ValueError("Choose between one and ten samples per book")
    detail = vault.series_detail(series_id)
    entities = canon.list_entities(series_id)
    selected = next((entity for entity in entities if entity["id"] == entity_id), None)
    if selected is None:
        raise FileNotFoundError("Entity not found in this series")
    if selected["kind"] != "character":
        raise ValueError("Character Minds evidence map requires a character")
    forms = _forms(selected)
    relevant = [volume for volume in detail["volumes"]
                if min_book <= volume["ordinal"] <= max_book]
    if len(relevant) > MAX_BOOKS:
        raise ValueError("Too many books in the selected range")
    other_characters = [
        (entity["name"], _forms(entity))
        for entity in entities if entity["kind"] == "character" and entity["id"] != entity_id
    ]
    results = []
    all_mentions = 0
    samples_kept = 0
    co_mentions = Counter()
    for volume in relevant:
        book_count = 0
        book_sources = []
        examples = []
        for source in volume["sources"]:
            record, content = vault.source_text(series_id, source["id"])
            points = _intervals(content, forms)
            book_count += len(points)
            if not points:
                continue
            book_sources.append(source["id"])
            saved = indexes.read(series_id, source["id"])
            # At most 4 samples per book by default, spread across the source
            # rather than taking only the first page. Stable deterministic rank.
            slots = min(limit_per_book - len(examples), len(points),
                        MAX_TOTAL_SAMPLES - samples_kept)
            if slots > 0:
                picks = sorted({min(len(points) - 1, int(i * len(points) / slots))
                                for i in range(slots)})
                for index in picks:
                    begin, end = points[index]
                    left, right, quote = _context(content, begin, end)
                    section = _section(saved, begin)
                    examples.append({
                        "source_id": source["id"], "source_hash": record["sha256"],
                        "mention_start": begin, "mention_end": end,
                        "excerpt_start": left, "excerpt_end": right,
                        "excerpt": quote, "mention": content[begin:end],
                        "section_index": section["index"] if section else None,
                        "section_title": section["title"] if section else None,
                        "verified_original_epub": bool(saved),
                    })
                    samples_kept += 1
            for name, aliases in other_characters:
                # Raw nearby *text* mentions are NOT a confirmed interaction.
                other_points = _intervals(content, aliases)
                j = 0
                for at, _ in points:
                    while j < len(other_points) and other_points[j][1] < at - 250:
                        j += 1
                    if j < len(other_points) and other_points[j][0] <= at + 250:
                        co_mentions[name] += 1
        all_mentions += book_count
        results.append({
            "book": volume["ordinal"], "volume": volume["title"],
            "mention_count": book_count,
            "source_count_with_mention": len(book_sources),
            "samples": examples,
        })
    return {
        "series_id": series_id, "entity_id": entity_id,
        "entity_name": selected["name"], "entity_kind": selected["kind"],
        "min_book": min_book, "max_book": max_book,
        "books_examined": len(relevant),
        "books_with_mentions": sum(row["mention_count"] > 0 for row in results),
        "total_literal_mentions": all_mentions,
        "books": results,
        "nearby_character_names": [
            {"name": name, "nearby_mention_count": count}
            for name, count in co_mentions.most_common(15)
        ],
        "source_verified": True, "author_approved_facts_created": 0,
        "limitations": (
            "Exact literal name/alias matches only. Mentions may occur in memories, "
            "dialogue, index pages, dreams, chapter titles or another context. "
            "Nearby character names do not prove an interaction or relationship. "
            "Unlisted aliases and pronouns are not counted."
        ),
    }
