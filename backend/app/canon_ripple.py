"""Project-local, author-controlled canon change impact ledger.

No model calls, cross-project reads, or automatic manuscript edits. Exact fact
matching is a discovery heuristic, not a contradiction determination.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .storage import get_project, project_root, read_text

MAX_DEBTS = 150
MAX_SCAN_FILES = 1000
MAX_SCAN_BYTES = 16_000_000
MAX_MATCHES = 120
STATE_FILE = "canon-ripples.json"
SEARCH_ROOTS = ("manuscript/", "characters/", "world/", "scenes/", "timeline/", "relationships/", "planning/", "summaries/", "style/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / STATE_FILE


def list_ripples(slug: str) -> list[dict]:
    path = _path(slug)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) > MAX_DEBTS:
        raise ValueError("Canon change ledger is invalid")
    if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in raw):
        raise ValueError("Canon change ledger contains invalid records")
    return raw


def _write(slug: str, records: list[dict]) -> None:
    if len(records) > MAX_DEBTS:
        raise ValueError("Canon ledger is full: resolve or archive items first")
    dest = _path(slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.with_suffix(".json.tmp")
    staging.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    staging.replace(dest)


def find_impacts(slug: str, old_fact: str, source_path: str = "") -> dict:
    """Bounded literal scan; a match is a *review candidate*, not proof of conflict."""
    project = get_project(slug)
    phrase = old_fact.strip()
    if len(phrase) < 3 or len(phrase) > 500:
        raise ValueError("Original fact must contain between 3 and 500 characters")
    if source_path and source_path not in project["files"]:
        raise ValueError("Source file is not in this project")
    files = sorted(
        path for path in project["files"]
        if path.startswith(SEARCH_ROOTS) and path.endswith((".md", ".txt", ".json", ".yaml", ".yml"))
    )
    truncated = len(files) > MAX_SCAN_FILES
    examined = 0
    total_bytes = 0
    matches: list[dict] = []
    matcher = re.compile(re.escape(phrase), flags=re.IGNORECASE)
    for relative in files[:MAX_SCAN_FILES]:
        content = read_text(slug, relative)
        size = len(content.encode("utf-8"))
        if total_bytes + size > MAX_SCAN_BYTES:
            truncated = True
            break
        total_bytes += size
        examined += 1
        occurrences = sum(1 for _ in matcher.finditer(content))
        if occurrences and relative != source_path:
            matches.append({"path": relative, "occurrences": occurrences, "review_status": "pending"})
            if len(matches) >= MAX_MATCHES:
                truncated = True
                break
    return {"matches": matches, "scanned_files": examined, "truncated": truncated, "method": "literal_case_insensitive"}


def create_ripple(slug: str, *, title: str, old_fact: str, proposed_fact: str,
                  source_path: str = "", rationale: str = "") -> dict:
    title = title.strip()
    proposed_fact = proposed_fact.strip()
    old_fact = old_fact.strip()
    rationale = rationale.strip()
    if not title or len(title) > 200 or not proposed_fact or len(proposed_fact) > 500:
        raise ValueError("Title and proposed fact are required within the length limits")
    if old_fact.casefold() == proposed_fact.casefold():
        raise ValueError("The proposed fact must differ from the original")
    if len(rationale) > 2000:
        raise ValueError("Rationale is too long")
    history = list_ripples(slug)
    # The record is a proposed change. No underlying canon file is edited.
    impact = find_impacts(slug, old_fact, source_path)
    record = {
        "id": uuid4().hex,
        "title": title,
        "old_fact": old_fact,
        "proposed_fact": proposed_fact,
        "source_path": source_path,
        "rationale": rationale,
        "status": "proposed",
        "created_at": _now(),
        "updated_at": _now(),
        **impact,
    }
    _write(slug, [record, *history])
    return record


def update_ripple(slug: str, ripple_id: str, *, action: str, path: str = "") -> dict:
    records = list_ripples(slug)
    record = next((item for item in records if item["id"] == ripple_id), None)
    if record is None:
        raise FileNotFoundError("Canon ripple not found")
    if action == "rescan":
        fresh = find_impacts(slug, record["old_fact"], record["source_path"])
        prior = {item["path"]: item for item in record["matches"]}
        for item in fresh["matches"]:
            if item["path"] in prior:
                item["review_status"] = prior[item["path"]].get("review_status", "pending")
        record.update(fresh)
    elif action == "approve":
        if record["status"] != "proposed":
            raise ValueError("Only proposed canon changes can be approved")
        record["status"] = "approved"
    elif action == "reject":
        if record["status"] != "proposed":
            raise ValueError("Only proposed canon changes can be rejected")
        record["status"] = "rejected"
    elif action == "mark_reviewed":
        if record["status"] != "approved":
            raise ValueError("Approve the proposed canon change before reviewing impacts")
        match = next((item for item in record["matches"] if item["path"] == path), None)
        if match is None:
            raise ValueError("Path is not an identified impact")
        match["review_status"] = "reviewed"
    elif action == "reopen_impact":
        match = next((item for item in record["matches"] if item["path"] == path), None)
        if match is None:
            raise ValueError("Path is not an identified impact")
        match["review_status"] = "pending"
    elif action == "resolve":
        if record["status"] != "approved":
            raise ValueError("Only approved canon changes can be resolved")
        if any(item["review_status"] != "reviewed" for item in record["matches"]):
            raise ValueError("Review each affected file before resolving the change")
        record["status"] = "resolved"
    else:
        raise ValueError("Unknown canon action")
    record["updated_at"] = _now()
    _write(slug, records)
    return record
