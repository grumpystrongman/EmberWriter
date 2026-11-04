"""Local-only Autopilot readiness and mechanical manuscript auditing.

This module is intentionally non-generative: it reads one project's documents,
stores only derived measurements within that project, never sends prompts to a
provider, and never rewrites the manuscript. Future agents can consume its
phase gates without bypassing author approval.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .development import load_development_state
from .prose_quality import diagnose_prose
from .storage import get_project, project_root, read_text

AUDIT_FILENAME = "autopilot-audits.json"
MAX_AUDITS = 20
MAX_CHAPTERS = 250
MAX_AUDIT_BYTES = 8_000_000
WORD_PATTERN = re.compile(r"\b[\w]+(?:['’-][\w]+)*\b", re.UNICODE)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _local_audit_file(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / AUDIT_FILENAME


def _safe_json_read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError("Autopilot history is invalid")
    return [item for item in obj if isinstance(item, dict)][:MAX_AUDITS]


def audit_history(slug: str) -> list[dict[str, Any]]:
    path = _local_audit_file(slug)
    # History contains only measurements and filenames, not manuscript text.
    return _safe_json_read(path)


def _snapshot(slug: str) -> dict[str, Any]:
    project = get_project(slug)
    paths = project["files"]
    # A placeholder created by new-project should not count as a full draft.
    drafts = sorted(p for p in paths if p.startswith("manuscript/") and p.endswith((".md", ".txt")))[:MAX_CHAPTERS]
    foundation = {
        "world": any(p.startswith("world/") and not p.endswith("README.md") for p in paths),
        "characters": any(p.startswith("characters/") and not p.endswith("README.md") for p in paths),
        "outline": any(p.startswith(("planning/", "scenes/", "timeline/")) and p.endswith((".md", ".json")) for p in paths),
        "style": any(p.startswith("style/") and p not in ("style/author-profile.md",) for p in paths),
    }
    results = []
    fingerprint = hashlib.sha256()
    for path in drafts:
        text = read_text(slug, path)
        fingerprint.update(path.encode("utf-8"))
        fingerprint.update(hashlib.sha256(text.encode("utf-8")).digest())
        word_count = len(WORD_PATTERN.findall(text))
        if len(text.encode("utf-8")) > MAX_AUDIT_BYTES:
            # Defensive bound for pathological input, not a quality judgment.
            raise ValueError("A manuscript chapter exceeds local audit limits")
        if word_count < 75:
            # Empty new-project placeholders and outline-only files are not drafts.
            status = "outline"
        else:
            status = "draft"
        sentences = [s.strip() for s in SENTENCE_PATTERN.split(text) if s.strip()]
        lengths = [len(WORD_PATTERN.findall(s)) for s in sentences]
        distinct_starts = Counter(
            " ".join(WORD_PATTERN.findall(s.lower())[:2]) for s in sentences if len(WORD_PATTERN.findall(s)) >= 2
        )
        issues = diagnose_prose(text)[:8] if status == "draft" else []
        if len(lengths) >= 5 and max(lengths) - min(lengths) <= 3:
            issues.append("Sentence lengths are very uniform; review cadence.")
        results.append({
            "path": path,
            "words": word_count,
            "status": status,
            "issue_count": len(issues),
            "issues": issues,
            "repeated_openings": sum(count - 1 for count in distinct_starts.values() if count > 2),
        })
    total_words = sum(x["words"] for x in results)
    drafted = [x for x in results if x["status"] == "draft"]
    development = load_development_state(slug)
    unresolved = [thread for thread in development.threads if thread.status.lower() not in ("resolved", "closed", "complete", "completed", "paid_off")]
    unplanned_payoffs = [thread.title for thread in unresolved if not thread.payoff.strip() and not thread.target_payoff_chapter]
    # Preserve source IDs but do not invent a payoff or infer that a thread was
    # resolved merely because its target chapter has already been drafted.
    return {
        "project_slug": slug,
        "project_name": project["name"],
        "fingerprint": fingerprint.hexdigest(),
        "foundation": foundation,
        "foundation_complete": sum(foundation.values()),
        "foundation_total": len(foundation),
        "chapters": results,
        "chapter_count": len(results),
        "drafted_count": len(drafted),
        "total_words": total_words,
        "issues_total": sum(x["issue_count"] for x in results),
        "open_threads": len(unresolved),
        "unplanned_payoffs": unplanned_payoffs[:100],
        "truncated": len(drafts) >= MAX_CHAPTERS,
    }


def _plan(snap: dict[str, Any]) -> list[dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    foundation = snap["foundation"]
    foundation_missing = [name.replace("_", " ") for name, ready in foundation.items() if not ready]
    phases.append({
        "id": "foundation",
        "label": "Foundation",
        "status": "ready" if not foundation_missing else "needs_attention",
        "summary": "Build the world, cast, outline and narrative voice.",
        "tasks": [f"Develop {item} material" for item in foundation_missing] or
                 ["Review canon and voice for consistency before drafting"],
    })
    if snap["unplanned_payoffs"]:
        phases[0]["tasks"].append(
            f"Plan payoffs for {len(snap['unplanned_payoffs'])} unresolved story promise(s)"
        )
    phases.append({
        "id": "draft",
        "label": "Draft",
        "status": "ready" if snap["drafted_count"] else "needs_attention",
        "summary": "Write chapters sequentially with author-controlled checkpoints.",
        "tasks": (
            [f"Develop {snap['chapter_count'] - snap['drafted_count']} outline or stub chapter(s)"] if snap["chapter_count"] > snap["drafted_count"] else []
        ) + (["No drafted chapters yet; start with the opening scene"] if not snap["drafted_count"] else
             ["Evaluate the next draft against the established story map"]),
    })
    phases.append({
        "id": "revise",
        "label": "Revise",
        "status": "needs_attention" if snap["issues_total"] else ("ready" if snap["drafted_count"] else "not_started"),
        "summary": "Triangulate mechanical prose findings with editorial and reader analysis.",
        "tasks": [
            f"Review {snap['issues_total']} mechanical finding(s); no edits were applied",
            "Use Editorial and Reader Studio for deeper, subjective critiques",
            "Approve every proposed manuscript revision before applying it",
        ] if snap["drafted_count"] else ["Draft chapters before running a revision cycle"],
    })
    phases.append({
        "id": "release",
        "label": "Release",
        "status": "not_started",
        "summary": "Prepare a typeset interior, cover, export, and optional narrated edition.",
        "tasks": ["Review Publishing Studio formats and metadata", "Approve release assets before export"],
    })
    return phases


def current_readiness(slug: str) -> dict[str, Any]:
    snap = _snapshot(slug)
    return {**snap, "phases": _plan(snap), "local_only": True, "manuscript_modified": False,
            "method": "deterministic mechanical scan; not an LLM literary score"}


def run_audit(slug: str) -> dict[str, Any]:
    report = current_readiness(slug)
    report["id"] = uuid4().hex
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    path = _local_audit_file(slug)
    previous = _safe_json_read(path)
    updated = [report, *previous][:MAX_AUDITS]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return report
