"""Deterministic local retrieval of *source passages* for long-novel continuity.

No vectors, embeddings, external API, generated summaries, or inferred canon.
The current chapter brief is matched to original prose paragraphs in earlier
approved chapters or pending author-review candidates. Returned snippets are
verbatim, attributed, bounded, and only evidence to consider, never truth claims.
"""
from __future__ import annotations

import re
from collections import Counter

TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
STOP = frozenset(
    ["the", "and", "then", "those", "these", "that", "this", "with", "from", "into", "were", "was", "are", "have", "has", "had", "they", "them", "their", "his", "her", "she", "him", "him", "who", "when", "where", "what", "which", "why", "how", "while", "before", "after", "every", "just", "very", "some", "other", "more", "than", "much", "each", "once", "also", "along", "about", "across", "again", "under", "over", "through", "without", "between", "against", "there", "here", "chapter", "scene", "story", "moments", "discover", "discovers", "discovery", "characters", "return", "returns", "happens", "happen", "must", "should", "would", "could", "will", "did", "been", "being"]
)
MAX_SCAN_CHARS = 550_000
MAX_SNIPPET = 520
MAX_RESULTS = 5


def _terms(value: str) -> list[str]:
    return [word.casefold() for word in TOKEN.findall(value) if word.casefold() not in STOP]


def related_passages(
    slug: str,
    state: dict,
    chapter_index: int,
    *,
    limit: int = MAX_RESULTS,
) -> list[dict]:
    if chapter_index < 2:
        return []
    # Local import avoids a module cycle; retrieval is called by book_studio.
    from .book_studio import _prior_chapter_text
    chapter = state["chapters"][chapter_index]
    query = _terms(chapter["title"] + " " + chapter["brief"])
    if not query:
        return []
    query_counts = Counter(query)
    if not query_counts:
        return []
    earlier = [entry for entry in state["chapters"][:chapter_index - 1]
               if entry["status"] in ("candidate", "approved")]
    candidates = []
    processed = 0
    for entry in reversed(earlier):
        if processed >= MAX_SCAN_CHARS:
            break
        text = _prior_chapter_text(slug, entry)
        if not text:
            continue
        remaining = max(0, MAX_SCAN_CHARS - processed)
        content = text[:remaining]
        processed += len(content)
        # Split into source paragraphs and preserve offsets for references.
        for match in re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", content):
            passage = match.group().strip()
            if len(passage) < 70:
                continue
            paragraph_terms = _terms(passage[:1800])
            matched = set(paragraph_terms) & query_counts.keys()
            # Require multiple distinct distinctive terms; generic word overlap
            # makes retrieved passages look important despite low relevance.
            if len(matched) < 2:
                continue
            if len(passage) > MAX_SNIPPET:
                # Center near the first matched term; preserve verbatim prose.
                found = next((m.start() for m in TOKEN.finditer(passage)
                              if m.group().casefold() in matched), 0)
                start = max(0, found - 100)
                end = min(len(passage), start + MAX_SNIPPET)
                snippet = passage[start:end].strip()
            else:
                start = 0
                snippet = passage
            if len(snippet) < 70:
                continue
            line = content.count("\n", 0, match.start() + start) + 1
            score = sum(1 + min(query_counts[token], 2) for token in matched)
            score += min(3, len(matched) - 2)
            candidates.append({
                "chapter": entry["number"],
                "title": entry["title"],
                "status": entry["status"],
                "line": line,
                "score": score,
                "matched_terms": sorted(matched)[:8],
                "excerpt": snippet,
            })
    # Largest number of shared terms first. Guarantee diversity by selecting
    # no more than one passage per old chapter.
    candidates.sort(key=lambda item: (-item["score"], -item["chapter"], item["line"]))
    chosen = []
    used = set()
    for item in candidates:
        if item["chapter"] in used:
            continue
        chosen.append(item)
        used.add(item["chapter"])
        if len(chosen) == max(1, min(limit, MAX_RESULTS)):
            break
    return chosen


def context_section(slug: str, state: dict, chapter_index: int) -> str:
    passages = related_passages(slug, state, chapter_index)
    if not passages:
        return ""
    lines = [
        "### Relevant earlier manuscript excerpts (verbatim, partial, not verified summaries)",
        "Treat these as evidence for continuity, not authorization to overwrite current author canon.",
    ]
    for item in passages:
        lines.append(
            f"Ch. {item['chapter']} {item['title']} ({item['status']}, source line {item['line']}): "
            + item["excerpt"].replace("\n", " ")
        )
    return "\n".join(lines)
