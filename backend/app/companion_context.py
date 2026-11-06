"""Bounded project-local evidence for the optional Ember writing companion.

No request ever sends an entire manuscript by default. Snippets are gathered only
after the author checks 'Use my writing for this answer'. Retrieval is read-only.
"""
from __future__ import annotations

import re
from pathlib import Path

from .memory import list_memory
from .storage import get_project, project_root, search_story

MAX_EVIDENCE = 7
MAX_TOTAL_CHARS = 4300
STOP_WORDS = {
    "about", "what", "where", "when", "which", "there", "their", "they", "this",
    "that", "have", "from", "with", "your", "does", "were", "would", "could",
    "should", "tell", "know", "character", "characters", "story", "book", "novel",
    "chapter", "scene", "writing", "please", "happened", "after", "before",
}


def keywords(question: str) -> str:
    tokens = re.findall(r"[\w'-]+", question.lower())
    words = [word for word in tokens if len(word) >= 3 and word not in STOP_WORDS]
    return " ".join(words[:12])


def project_snapshot(slug: str) -> dict:
    project = get_project(slug)
    root = project_root(slug)
    files = project["files"]
    documents = [p for p in files if p.startswith("manuscript/") and p.endswith((".md", ".txt"))]
    characters = [Path(p).stem.replace("-", " ") for p in files
                  if p.startswith("characters/") and p.endswith((".md", ".txt"))
                  and Path(p).name.casefold() != "readme.md"]
    index = root / ".ember" / "writing-templates.json"
    choices: dict = {}
    if index.is_file():
        try:
            import json
            data = json.loads(index.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                choices = data
        except (OSError, ValueError):
            pass
    return {
        "name": project["name"],
        "description": project.get("description", "")[:400],
        "manuscript_files": len(documents),
        "chapter_names": [Path(p).stem.replace("-", " ") for p in documents[:24]],
        "character_names": characters[:30],
        "writing_formats": sorted({row.get("format") for row in choices.values()
                                   if isinstance(row, dict) and isinstance(row.get("format"), str)}),
    }


def retrieve(slug: str, question: str) -> list[dict]:
    terms = keywords(question)
    if not terms:
        return []
    evidence: list[dict] = []
    remaining = MAX_TOTAL_CHARS
    seen: set[tuple[str, str]] = set()

    # Memory facts are potentially stale/unapproved. Show provenance and caveat.
    for item in list_memory(slug, query=terms, limit=4):
        if remaining < 120 or len(evidence) >= MAX_EVIDENCE:
            break
        path = item.get("source_path") or ""
        snippet = f"{item['subject']}: {item['predicate']} {item['object']}".strip()
        if (path, snippet) in seen:
            continue
        clipped = snippet[:min(520, remaining)]
        evidence.append({"path": path, "excerpt": clipped, "kind": "extracted_note",
                         "status": "unverified_memory"})
        seen.add((path, snippet))
        remaining -= len(clipped)

    for item in search_story(slug, terms, limit=8):
        if remaining < 100 or len(evidence) >= MAX_EVIDENCE:
            break
        path = str(item.get("path", ""))
        if path.startswith(("summaries/", "style/")):
            continue
        snippet = str(item.get("excerpt", "")).strip()
        if (path, snippet) in seen:
            continue
        clipped = snippet[:min(720, remaining)]
        evidence.append({"path": path, "excerpt": clipped, "kind": "source_passage",
                         "status": "author_file_not_validated_as_canon"})
        seen.add((path, snippet))
        remaining -= len(clipped)

    return evidence
