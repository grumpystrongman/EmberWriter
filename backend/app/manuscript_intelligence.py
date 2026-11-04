"""Whole-novel intelligence, based on explicit author-provided subjects and evidence.

Mechanical chapter analysis is deliberately descriptive. Presence is exact
token/phrase matching, not proof of character agency or narrative resolution.
The story promise ledger records the author's decisions; it never silently
edits canon or declares a plot promise fulfilled.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .book_studio import candidate, load_state
from .quality_clinic import check_text
from .storage import get_project, project_root, read_text

MAX_CHAPTERS = 100
MAX_BYTES = 8_000_000
MAX_TERMS = 30
MAX_PROMISES = 120
WORD = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")
QUOTE = re.compile(r'["“][^"”\n]{3,}["”]')
STOP = {"the", "and", "that", "with", "from", "this", "have", "were", "they",
        "she", "his", "her", "was", "you", "for", "not", "but", "had", "are",
        "their", "would", "could", "into", "when", "then", "there", "them"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ledger_file(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "manuscript-promises.json"


def _read_ledger(slug: str) -> list[dict]:
    path = _ledger_file(slug)
    if not path.is_file():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or len(entries) > MAX_PROMISES:
        raise ValueError("Story promise ledger is invalid")
    return entries


def _save_ledger(slug: str, ledger: list[dict]):
    path = _ledger_file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def list_promises(slug: str) -> list[dict]:
    return _read_ledger(slug)


def create_promise(slug: str, title: str, tracking_phrase: str, intention: str = "") -> dict:
    title, tracking_phrase, intention = title.strip(), tracking_phrase.strip(), intention.strip()
    if not title or len(title) > 180 or not 3 <= len(tracking_phrase) <= 150 or len(intention) > 1000:
        raise ValueError("Promise requires title (<=180) and tracking phrase (3-150 characters)")
    records = _read_ledger(slug)
    if len(records) >= MAX_PROMISES:
        raise ValueError("Story promise ledger is full")
    record = {
        "id": uuid4().hex, "title": title, "tracking_phrase": tracking_phrase,
        "intention": intention, "status": "open", "resolution_note": "",
        "created_at": _now(), "updated_at": _now(),
    }
    _save_ledger(slug, [record, *records])
    return record


def update_promise(slug: str, promise_id: str, status: str, resolution_note: str = "") -> dict:
    if status not in ("open", "resolved", "abandoned") or len(resolution_note) > 1500:
        raise ValueError("Invalid promise status or resolution note")
    entries = _read_ledger(slug)
    record = next((item for item in entries if item.get("id") == promise_id), None)
    if record is None:
        raise FileNotFoundError("Story promise not found")
    record["status"] = status
    record["resolution_note"] = resolution_note.strip()
    record["updated_at"] = _now()
    _save_ledger(slug, entries)
    return record


def _chapters(slug: str) -> list[dict]:
    project = get_project(slug)
    state = load_state(slug)
    chapters = []
    if state.get("configured"):
        # Prevent duplicate counting of Book Studio candidates and their
        # separately-approved manuscript copies.
        for ch in state["chapters"]:
            number = ch["number"]
            if ch["status"] not in ("candidate", "approved"):
                continue
            if ch["status"] == "approved":
                path = f"manuscript/book-studio/chapter-{number:03d}.md"
                if path not in project["files"]:
                    continue
                content = read_text(slug, path)
            else:
                content = candidate(slug, number)["content"]
                path = f"book-studio:candidate:{number}"
            chapters.append({"path": path, "title": ch["title"], "text": content, "status": ch["status"]})
    # Include hand-authored manuscripts outside the Book Studio output folder.
    for path in sorted(project["files"]):
        if path.startswith("manuscript/") and not path.startswith("manuscript/book-studio/") and path.lower().endswith((".md", ".txt")) and Path(path).name.lower() != "readme.md":
            content = read_text(slug, path)
            # The untouched starter page is not a meaningful manuscript chapter.
            if path == "manuscript/chapter-001.md" and content.strip() == ("# Chapter 1\n\nBegin " + project["name"] + " here."):
                continue
            chapters.append({"path": path, "title": Path(path).stem, "text": content, "status": "authored"})
    return chapters


def _occurrences(text: str, phrase: str) -> list[dict]:
    pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.I)
    hits = []
    for match in pattern.finditer(text):
        if len(hits) >= 4:
            break
        begin, end = match.span()
        hits.append({"line": text.count("\n", 0, begin) + 1,
                     "excerpt": text[max(0, begin - 65):min(len(text), end + 75)].replace("\n", " ").strip()})
    return hits


def analyze(slug: str, subjects: list[str] | None = None) -> dict:
    subjects = subjects or []
    if len(subjects) > MAX_TERMS or any(not 2 <= len(s.strip()) <= 90 for s in subjects):
        raise ValueError("Track up to 30 names or phrases of 2-90 characters")
    chapters = _chapters(slug)
    if len(chapters) > MAX_CHAPTERS:
        raise ValueError("Novel exceeds 100 chapter documents; narrow the project before scanning")
    total_bytes = sum(len(ch["text"].encode("utf-8")) for ch in chapters)
    if total_bytes > MAX_BYTES:
        raise ValueError("Manuscript exceeds the local 8 MB analysis limit")
    names = list(dict.fromkeys(s.strip() for s in subjects if s.strip()))
    promises = _read_ledger(slug)
    chapter_rows = []
    phrases_by_chapter = []
    for index, chapter in enumerate(chapters, 1):
        text = chapter["text"]
        quality = check_text(text)["metrics"]
        words = WORD.findall(text)
        lowered = [word.casefold() for word in words]
        repeated = Counter(tuple(lowered[pos:pos + 4])
                           for pos in range(max(0, len(lowered) - 3))
                           if sum(word not in STOP and len(word) >= 3 for word in lowered[pos:pos + 4]) >= 2)
        phrases_by_chapter.append(repeated)
        chapter_rows.append({
            "index": index, "path": chapter["path"], "title": chapter["title"],
            "status": chapter["status"], "words": quality["words"],
            "average_sentence_words": quality["average_sentence_words"],
            "dialogue_passages": quality["dialogue_passages"],
            "mechanical_flags": quality["findings"], "unique_word_ratio": quality["unique_word_ratio"],
            "fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "tracked_subjects": [
                {"name": name, "evidence": _occurrences(text, name)}
                for name in names if _occurrences(text, name)
            ],
        })
    repeated_across = Counter()
    for counts in phrases_by_chapter:
        for phrase in counts:
            repeated_across[phrase] += 1
    cross_chapter_echoes = [
        {"phrase": " ".join(phrase), "chapters": freq,
         "references": [chapter_rows[idx]["path"] for idx, c in enumerate(phrases_by_chapter) if phrase in c][:12]}
        for phrase, freq in repeated_across.most_common(150)
        if freq >= 2
    ][:24]
    promise_rows = []
    for item in promises:
        references = []
        for chapter in chapters:
            hits = _occurrences(chapter["text"], item["tracking_phrase"])
            if hits:
                references.append({"path": chapter["path"], "evidence": hits})
        promise_rows.append({**item, "references": references[:60], "reference_count": len(references),
                             "automatically_resolved": False})
    word_counts = [row["words"] for row in chapter_rows]
    average = sum(word_counts) / len(word_counts) if word_counts else 0
    return {
        "chapters": chapter_rows, "total_words": sum(word_counts),
        "chapter_count": len(chapter_rows), "average_chapter_words": round(average),
        "long_chapters": [r["path"] for r in chapter_rows if average and r["words"] > average * 1.7],
        "short_chapters": [r["path"] for r in chapter_rows if average and r["words"] < average * .5],
        "subject_names": names, "cross_chapter_echoes": cross_chapter_echoes,
        "promises": promise_rows, "scanned_bytes": total_bytes,
        "limitations": "Literal evidence and descriptive metrics only; presence is not character agency, foreshadowing, pacing quality, or proof that a plot thread was resolved.",
    }
