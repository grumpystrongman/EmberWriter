"""Read-only source structure from literal headings, never guessed story chronology.

Exact source character offsets, immutable snapshot fingerprint and conservative
confidence. No inference about POV, story time or chapter semantics.
"""
from __future__ import annotations

import re

from . import series_vault as vault

MAX_HEADINGS = 400
HEADING = re.compile(
    r"(?im)^(?P<title>[ \t]*(?:"
    r"(?:chapter|part|book|section)[ \t]+(?:[0-9]{1,4}|[IVXLCDM]{1,12})"
    r"(?:[ \t]*[:\-—][ \t]*[^\r\n]{1,65})?"
    r"|(?:prologue|epilogue|interlude)[ \t]*(?::[ \t]*[^\r\n]{1,65})?"
    r"|#{1,3}[ \t]+[^\r\n]{2,70}"
    r"))[ \t]*$"
)
MAX_TITLE_CHARS = 85


def sections(series_id: str, source_id: str, *, position: int | None = None) -> dict:
    source, content = vault.source_text(series_id, source_id)
    if position is not None and not 0 <= position < len(content):
        raise ValueError("Selected source character is outside this source")
    headings = []
    for match in HEADING.finditer(content):
        title = match.group("title").strip().lstrip("#").strip()
        if len(title) > MAX_TITLE_CHARS:
            continue
        headings.append((match.start(), title))
        if len(headings) > MAX_HEADINGS:
            break
    truncated = len(headings) > MAX_HEADINGS
    headings = headings[:MAX_HEADINGS]
    boundaries = []
    if headings:
        if headings[0][0] > 0:
            boundaries.append((0, "Opening / front matter (unverified heading)", False))
        for offset, title in headings:
            boundaries.append((offset, title, True))
    else:
        boundaries = [(0, "Whole source (no reliable chapter headings detected)", False)]
    results = []
    for index, (start, title, detected) in enumerate(boundaries):
        end = (boundaries[index + 1][0]
               if index + 1 < len(boundaries) else len(content))
        results.append({
            "index": index + 1, "title": title,
            "start": start, "end": end, "characters": end - start,
            "heading_detected": detected,
            "confidence": "explicit_heading" if detected else "unsegmented_or_front_matter",
            "author_confirmed": False,
        })
    selected = next((
        row["index"] for row in results
        if position is not None and row["start"] <= position < row["end"]
    ), None)
    return {
        "series_id": series_id, "source_id": source_id, "source_hash": source["sha256"],
        "book": source["ordinal"], "source_length": len(content),
        "sections": results, "selected_section": selected,
        "heading_limit_reached": truncated,
        "source_text_returned": False,
        "story_sequence_inferred": False,
        "disclaimer": (
            "Structural headings and character coordinates are not in-world time. "
            "Use author-reviewed book and scene chronology for canon."
        ),
    }
