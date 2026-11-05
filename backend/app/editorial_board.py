"""Whole-book editorial triage with source-bound batch edits.

The board combines deterministic prose and Style Bible scans, records a
repeatable scan snapshot, and proposes fixes without changing source text.
Applying a selected collection is explicit and all-or-nothing per chapter:
the entire source fingerprint and each proposed span must still match.
Author-owned snapshots are created before changing any file.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .book_reviews import history as reader_history
from .book_studio import edit_candidate
from .manuscript_intelligence import _chapters
from .prose_editor import _get as get_chapter
from .prose_editor import analyze as prose_analyze
from .prose_editor import analyze_text as prose_analyze_text
from .storage import get_project, project_root, save_text
from .story_arc_investigator import overview as arc_overview
from .style_bible import audit as style_audit

MAX_CHAPTERS = 120
MAX_BYTES = 12_000_000
MAX_ISSUES = 6000
MAX_APPLY = 100

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _now() -> str:
    return datetime.now(UTC).isoformat()

def _directory(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "editorial-board"

def _history_file(slug: str) -> Path:
    return _directory(slug) / "history.json"

def history(slug: str) -> list[dict]:
    path = _history_file(slug)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Editorial scan history is invalid")
    return data[:30]

def _save_history(slug: str, data: list[dict]):
    path = _history_file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data[:30], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def _source_book(slug: str) -> list[dict]:
    chapters = _chapters(slug)
    size = sum(len(ch["text"].encode("utf-8")) for ch in chapters)
    if len(chapters) > MAX_CHAPTERS or size > MAX_BYTES:
        raise ValueError("Editorial batch scan supports up to 120 chapters and 12 MB of text")
    return chapters

def _board(slug: str, *, perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    chapters = _source_book(slug)
    style = style_audit(slug)
    arcs = arc_overview(slug)
    arc_status = {row["path"]: row["analysis"] for row in arcs["chapters"]}
    by_chapter: dict[str, list[dict]] = {}
    for finding in style["findings"]:
        by_chapter.setdefault(finding["path"], []).append({
            "id": "style:" + finding["id"], "origin": "style", "category": finding["category"],
            "title": "Style Bible: " + finding["phrase"], "excerpt": finding["excerpt"],
            "line": finding["line"], "path": finding["path"],
            "decision": "dismissed" if finding["dismissed"] else "pending",
            "source_hash": finding["source_hash"], "suggestion": finding.get("preferred") or None,
            "mechanical": False,
        })
    rows = []
    total_prose = 0
    for chapter in chapters:
        path = chapter["path"]
        report = prose_analyze_text(slug, path, chapter["text"], chapter["status"], perspective, tense)
        pending = []
        for issue in report["findings"]:
            pending.append({
                "id": "prose:" + issue["id"], "origin": "prose", "category": issue["rule"],
                "title": issue["title"], "excerpt": issue["excerpt"], "line": issue["line"],
                "path": path, "decision": issue["decision"],
                "source_hash": report["source_hash"], "suggestion": issue["suggested"],
                "mechanical": issue["suggested"] is not None,
                "start": issue["start"], "end": issue["end"], "matched": issue["matched"],
            })
        total_prose += len(pending)
        entries = pending + by_chapter.get(path, [])
        chapter_number = None
        if path.startswith("book-studio:candidate:"):
            chapter_number = int(path.rsplit(":", 1)[1])
        else:
            match = re.fullmatch(r"manuscript/book-studio/chapter-(\d{3})\.md", path)
            if match:
                chapter_number = int(match.group(1))
        reviews = reader_history(slug, chapter_number)["reviews"] if chapter_number else []
        current_reviews = [review for review in reviews if not review["stale"]]
        rows.append({
            "path": path, "title": chapter["title"], "status": chapter["status"],
            "words": len(chapter["text"].split()), "fingerprint": _hash(chapter["text"]),
            "outstanding": sum(x["decision"] == "pending" for x in entries),
            "dismissed": sum(x["decision"] == "dismissed" for x in entries),
            "fixable": sum(x["decision"] == "pending" and x["mechanical"] for x in entries),
            "reader_reviews": len(current_reviews),
            "reader_findings_pending": sum(sum(f["decision"] == "pending" for f in review["findings"])
                                          for review in current_reviews),
            "story_arc_reviewed": bool(arc_status.get(path)),
            "findings": entries,
        })
    issue_count = sum(len(ch["findings"]) for ch in rows)
    if issue_count > MAX_ISSUES:
        raise ValueError("Editorial scan exceeds 6,000 observations; narrow style rules before rescanning")
    return {
        "chapters": rows, "chapter_count": len(rows),
        "total_words": sum(ch["words"] for ch in rows),
        "outstanding": sum(ch["outstanding"] for ch in rows),
        "dismissed": sum(ch["dismissed"] for ch in rows),
        "fixable": sum(ch["fixable"] for ch in rows),
        "reader_coverage": sum(ch["reader_reviews"] > 0 for ch in rows),
        "story_arc_coverage": sum(ch["story_arc_reviewed"] for ch in rows),
        "style_truncated": style["truncated"],
        "scan_config": {"perspective": perspective, "tense": tense},
        "limitations": (
            "Offline deterministic prose and exact terminology checks; neither "
            "a professional grammar engine nor an AI literary score. All changes "
            "require author approval and a matching source fingerprint."
        ),
    }

def scan(slug: str, perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    board = _board(slug, perspective=perspective, tense=tense)
    snapshot = {
        "id": uuid4().hex, "at": _now(), "chapters": board["chapter_count"],
        "words": board["total_words"], "outstanding": board["outstanding"],
        "dismissed": board["dismissed"], "fixable": board["fixable"],
        "perspective": perspective, "tense": tense,
        "chapter_fingerprints": {ch["path"]: ch["fingerprint"] for ch in board["chapters"]},
    }
    _save_history(slug, [snapshot, *history(slug)])
    return {**board, "scan_id": snapshot["id"], "scanned_at": snapshot["at"]}

def report(slug: str, perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    return _board(slug, perspective=perspective, tense=tense)

def _edits_for(slug: str, path: str, ids: list[str], perspective: str, tense: str,
               source_hash: str) -> tuple[str, str, list[dict]]:
    if not 1 <= len(ids) <= MAX_APPLY or len(set(ids)) != len(ids):
        raise ValueError("Select 1 to 100 distinct mechanical corrections")
    original, status = get_chapter(slug, path)
    if _hash(original) != source_hash:
        raise ValueError("The chapter changed after review. Rescan before applying corrections.")
    analysis = prose_analyze(slug, path, perspective, tense)
    valid = {"prose:" + f["id"]: f for f in analysis["findings"]
             if f["suggested"] is not None and f["decision"] == "pending"}
    selections = []
    for identifier in ids:
        if identifier not in valid:
            raise ValueError("Selected correction is not a current, pending mechanical suggestion")
        selections.append(valid[identifier])
    positions = sorted(selections, key=lambda item: item["start"])
    for i, finding in enumerate(positions):
        if original[finding["start"]:finding["end"]] != finding["matched"]:
            raise ValueError("A selected evidence span no longer matches the manuscript")
        if i and finding["start"] < positions[i-1]["end"]:
            raise ValueError("Selected corrections overlap; apply one at a time")
    changed = original
    for finding in reversed(positions):
        changed = changed[:finding["start"]] + finding["suggested"] + changed[finding["end"]:]
    return original, changed, positions

def preview(slug: str, path: str, ids: list[str], source_hash: str,
            perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    original, changed, findings = _edits_for(slug, path, ids, perspective, tense, source_hash)
    return {
        "path": path, "source_hash": source_hash, "proposed_hash": _hash(changed),
        "original": original, "proposed": changed,
        "changes": [{"start": f["start"], "before": f["matched"], "after": f["suggested"],
                     "rule": f["rule"], "line": original.count("\n", 0, f["start"]) + 1}
                    for f in findings],
        "count": len(findings),
        "warning": "Preview only. No manuscript document has been edited.",
    }

def apply(slug: str, path: str, ids: list[str], source_hash: str, proposed_hash: str,
          perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    original, changed, findings = _edits_for(slug, path, ids, perspective, tense, source_hash)
    if _hash(changed) != proposed_hash:
        raise ValueError("Proposed revision has changed. Generate a fresh preview.")
    if changed == original:
        raise ValueError("No changes to apply")
    if path.startswith("book-studio:candidate:"):
        edit_candidate(slug, int(path.rsplit(":", 1)[1]), changed)
    else:
        save_text(slug, path, changed)
    log = _directory(slug) / "approved-batches.json"
    prior = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    prior = [{
        "id": uuid4().hex, "at": _now(), "path": path,
        "before": _hash(original), "after": _hash(changed),
        "changes": [{"rule": f["rule"], "before": f["matched"], "after": f["suggested"]}
                    for f in findings],
    }, *prior][:100]
    log.parent.mkdir(parents=True, exist_ok=True)
    tmp = log.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(prior, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(log)
    return {
        "applied": True, "path": path, "count": len(findings),
        "original_hash": source_hash, "current_hash": _hash(changed),
        "snapshot_created": True,
    }

def markdown(slug: str, perspective: str = "unspecified", tense: str = "unspecified") -> str:
    board = _board(slug, perspective=perspective, tense=tense)
    lines = ["# Whole-Book Editorial Board", "",
             f"Chapters: {board['chapter_count']}; words: {board['total_words']}.",
             f"Outstanding: {board['outstanding']}; dismissed: {board['dismissed']}; safely fixable: {board['fixable']}.",
             "", "> " + board["limitations"], ""]
    for chapter in board["chapters"]:
        lines.extend([f"## {chapter['title']}", f"Source: {chapter['path']}",
                      f"Pending: {chapter['outstanding']}; author-dismissed: {chapter['dismissed']}.", ""])
        for finding in chapter["findings"]:
            if finding["decision"] == "pending":
                lines.append(f"- L{finding['line']} [{finding['origin']}/{finding['category']}]: "
                             f"{finding['title']} — {finding['excerpt']}")
        lines.append("")
    return "\n".join(lines)


def freshness(slug: str) -> dict:
    """Check whether the most recent saved editorial baseline still covers the book."""
    saved = history(slug)
    if not saved:
        return {"scanned": False, "current": False, "changed": [], "reason": "No whole-book editorial baseline saved"}
    baseline = saved[0]
    current = {ch["path"]: _hash(ch["text"]) for ch in _source_book(slug)}
    old = baseline.get("chapter_fingerprints", {})
    if not isinstance(old, dict):
        raise ValueError("Editorial scan baseline is invalid")
    changed = sorted(path for path in set(old) | set(current) if old.get(path) != current.get(path))
    return {
        "scanned": True, "current": not changed, "changed": changed[:100],
        "scan_id": baseline["id"], "scanned_at": baseline["at"],
        "change_signature": _hash("|".join(f"{path}:{current.get(path, '<deleted>')}" for path in changed)),
        "reason": "Chapter contents changed after the last book-wide editorial review" if changed else "Scan baseline covers current source text",
    }
