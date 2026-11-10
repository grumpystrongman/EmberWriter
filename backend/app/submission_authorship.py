"""Private evidence review of the rendered files in a submission handoff."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from .provenance_store import authorship_evidence

WORD = re.compile(r"[^\W_]+", re.UNICODE)
WINDOW = 8
MAX_EXCERPTS = 50


def _words(text: str) -> list[str]:
    return WORD.findall(text.casefold())


def _windows(words: list[str], size: int):
    for start in range(len(words) - size + 1):
        yield tuple(words[start:start + size])


def _rendered_text(path: Path) -> str:
    if path.suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if path.suffix == ".docx":
        return "\n".join(p.text for p in Document(path).paragraphs)
    return path.read_text(encoding="utf-8")


def submission_authorship(slug: str, paths: list[Path], fingerprints: list[dict]) -> dict:
    events = authorship_evidence(slug)
    by_phrase: dict[tuple[str, ...], list[dict]] = {}
    for event in events:
        output = event["output_text"]
        if not output:
            continue
        words = _words(output)
        if not words:
            continue
        size = min(WINDOW, len(words))
        original = set(_windows(_words(event["original_text"] or ""), size))
        for phrase in set(_windows(words, size)) - original:
            by_phrase.setdefault(phrase, []).append(event)

    matching_events: set[str] = set()
    excerpts: list[dict] = []
    files: list[dict] = []
    for path, fingerprint in zip(paths, fingerprints, strict=True):
        if path.suffix not in {".pdf", ".docx", ".txt"}:
            continue
        text = _rendered_text(path)
        tokens = list(WORD.finditer(text))
        words = [token.group().casefold() for token in tokens]
        hits: dict[str, list[tuple[int, int, dict]]] = {}
        for start, phrase in enumerate(_windows(words, WINDOW)):
            for event in by_phrase.get(phrase, ()):
                spans = hits.setdefault(event["id"], [])
                if spans and start <= spans[-1][1]:
                    spans[-1] = (spans[-1][0], start + WINDOW, event)
                else:
                    spans.append((start, start + WINDOW, event))
        # Very short outputs are only compared to complete assets to avoid
        # treating a common phrase elsewhere in the book as evidence.
        if 0 < len(words) < WINDOW:
            for event in by_phrase.get(tuple(words), ()):
                hits[event["id"]] = [(0, len(words), event)]

        matching_events.update(hits)
        spans = sorted((span for group in hits.values() for span in group), key=lambda hit: hit[0])
        files.append({
            **fingerprint,
            "matched_events": len(hits),
            "matched_passages": len(spans),
            "text_available": bool(words),
        })
        for start, end, event in spans:
            if len(excerpts) >= MAX_EXCERPTS:
                break
            end = min(end, start + 30)
            excerpts.append({
                "file": path.name,
                "source": event["active_file"],
                "mode": event["mode"],
                "event_id": event["id"],
                "excerpt": text[tokens[start].start():tokens[end - 1].end()],
                "original_excerpt": (event["original_text"] or "")[:500],
            })

    return {
        "schema_version": 1,
        "files": files,
        "recorded_assistance": dict(Counter(event["mode"] for event in events)),
        "legacy_events_without_wording": sum(
            event["output_text"] is None and event["mode"] in {"write", "continue", "rewrite"}
            for event in events
        ),
        "matched_events": len(matching_events),
        "excerpts": excerpts,
        "excerpts_omitted": sum(file["matched_passages"] for file in files) - len(excerpts),
        "coverage": (
            "Matches compare packet text with recorded AI wording. They are review leads. "
            "Unmatched or imported text has unverified origin. Short or edited wording, "
            "external AI use, and older events without captured wording can escape matching. "
            "Project assistance history includes feedback and drafts that may never have been used."
        ),
    }
