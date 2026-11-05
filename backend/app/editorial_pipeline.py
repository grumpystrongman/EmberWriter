"""Source-anchored, author-approved, book-wide editorial revision pipeline.

The pipeline never changes manuscript during proposal generation. A reviewed
batch applies nonoverlapping edits against exact chapter SHA-256 hashes and
creates a revision checkpoint per changed document; failures roll text back.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .editorial import get_editorial_run, list_editorial_findings, run_editorial
from .editorial_fix import _target_span, propose_editorial_fix
from .editorial_models import EditorialFixRequest, EditorialRunRequest
from .models import ProviderConfig
from .revisions import record_revision
from .storage import get_project, project_root, read_text, save_text

_LOCKS: dict[str, threading.RLock] = {}
MAX_BATCH = 80


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "editorial-revision-pipeline.json"


def _read(slug: str) -> dict | None:
    file = _path(slug)
    if not file.exists():
        return None
    data = json.loads(file.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("items"), list):
        raise ValueError("Invalid editorial revision pipeline")
    return data


def _write(slug: str, data: dict) -> dict:
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return data


def status(slug: str) -> dict:
    payload = _read(slug)
    if payload is None:
        return {"status": "not_started", "items": [], "version": 1}
    if payload["status"] == "proposing":
        # Safe after crashes: no manuscript is ever changed during proposal.
        payload = {**payload, "status": "interrupted"}
    return payload


def plan(slug: str, run_id: str, limit: int = 40) -> dict:
    if not 1 <= limit <= MAX_BATCH:
        raise ValueError("Editorial batch limit must be 1-80")
    get_editorial_run(slug, run_id)
    findings = list_editorial_findings(slug, run_id=run_id, status="open", limit=5000)
    selected = []
    skipped = []
    occupied = defaultdict(list)
    for finding in findings:
        if len(selected) >= limit:
            break
        path = finding["path"]
        if finding.get("stale"):
            skipped.append({"finding_id": finding["id"], "reason": "Source changed"})
            continue
        source = read_text(slug, path)
        digest = _sha(source)
        if digest != finding["source_hash"]:
            skipped.append({"finding_id": finding["id"], "reason": "Source hash changed"})
            continue
        start, end = _target_span(source, finding)
        if not source[start:end].strip():
            continue
        if any(start < old_end and old_start < end for old_start, old_end in occupied[path]):
            skipped.append({"finding_id": finding["id"], "reason": "Overlaps a higher-priority edit"})
            continue
        occupied[path].append((start, end))
        selected.append({
            "finding_id": finding["id"], "path": path,
            "start": start, "end": end, "source_hash": digest,
            "original": source[start:end], "report_id": finding["report_id"],
            "replacement": None, "rationale": "", "error": "",
        })
    if not selected:
        raise ValueError("No current nonoverlapping editorial findings were found")
    record = {
        "version": 1, "id": uuid4().hex, "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "planned", "items": selected, "skipped": skipped,
        "message": "Review the staged changes before approving manuscript edits.",
    }
    with _LOCKS.setdefault(slug, threading.RLock()):
        existing = _read(slug)
        if existing and existing["status"] in {"proposing", "applying"}:
            raise ValueError("An editorial pipeline is already active")
        return _write(slug, record)


async def propose(slug: str, plan_id: str, provider: ProviderConfig,
                  instruction: str = "") -> dict:
    if len(instruction) > 2000:
        raise ValueError("Editorial instruction is too long")
    with _LOCKS.setdefault(slug, threading.RLock()):
        data = _read(slug)
        if not data or data["id"] != plan_id:
            raise FileNotFoundError("Editorial pipeline not found")
        if data["status"] not in {"planned", "interrupted", "proposed"}:
            raise ValueError("Editorial pipeline is not ready for proposal generation")
        data["status"] = "proposing"
        _write(slug, data)
    from .local_resources import reservation
    for item in data["items"]:
        if item["replacement"] is not None or item["error"]:
            continue
        try:
            async with reservation():
                proposal = await propose_editorial_fix(slug, EditorialFixRequest(
                    finding_id=item["finding_id"], provider=provider, instruction=instruction))
            if (proposal.path != item["path"] or proposal.source_hash != item["source_hash"]
                or (proposal.target_start, proposal.target_end) != (item["start"], item["end"])
                or proposal.original != item["original"]):
                raise ValueError("Proposal drifted from the source-anchored editorial plan")
            item["replacement"] = proposal.replacement
            item["rationale"] = proposal.rationale
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
        with _LOCKS.setdefault(slug, threading.RLock()):
            latest = _read(slug)
            if latest is None or latest["id"] != plan_id:
                raise ValueError("Editorial plan changed while generating revisions")
            # Persist each proposed item for crash recovery and user review.
            latest["items"] = data["items"]
            _write(slug, latest)
        await asyncio.sleep(0)
    with _LOCKS.setdefault(slug, threading.RLock()):
        data["status"] = "proposed"
        data["message"] = "Proposals staged. No manuscript has been changed."
        return _write(slug, data)


def apply(slug: str, plan_id: str, approved_ids: list[str], confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("Explicit author approval is required before editing manuscripts")
    if not approved_ids or len(approved_ids) > MAX_BATCH or len(set(approved_ids)) != len(approved_ids):
        raise ValueError("Choose distinct proposed editorial fixes to approve")
    lock = _LOCKS.setdefault(slug, threading.RLock())
    with lock:
        data = _read(slug)
        if not data or data["id"] != plan_id:
            raise FileNotFoundError("Editorial pipeline not found")
        if data["status"] != "proposed":
            raise ValueError("Generate and review the editorial proposals before applying")
        approvals = set(approved_ids)
        all_ids = {item["finding_id"] for item in data["items"]}
        if approvals - all_ids:
            raise ValueError("One or more selected approvals are not part of this plan")
        by_path = defaultdict(list)
        for item in data["items"]:
            if item["finding_id"] not in approvals:
                continue
            if not isinstance(item["replacement"], str) or item["error"]:
                raise ValueError("Selected edit is not a completed proposal")
            if item["replacement"] == item["original"]:
                continue
            by_path[item["path"]].append(item)
        if not by_path:
            raise ValueError("There are no changed manuscript passages to approve")
        # Validate ALL documents before touching any one of them.
        originals = {}
        updates = {}
        for path, items in by_path.items():
            source = read_text(slug, path)
            if any(item["source_hash"] != _sha(source) for item in items):
                raise ValueError(f"{path} changed after editorial proposal; regenerate the batch")
            ordered = sorted(items, key=lambda x: x["start"], reverse=True)
            previous_start = len(source)
            content = source
            for item in ordered:
                start, end = item["start"], item["end"]
                if not (0 <= start < end <= previous_start and source[start:end] == item["original"]):
                    raise ValueError("Editorial edits overlap or source anchor changed")
                content = content[:start] + item["replacement"] + content[end:]
                previous_start = start
            originals[path] = source
            updates[path] = content
        data["status"] = "applying"
        _write(slug, data)
        changed = []
        try:
            for path, updated in updates.items():
                save_text(slug, path, updated)
                changed.append(path)
                record_revision(slug, path, updated, source="editorial_batch",
                                note=f"Author-approved editorial batch {plan_id}", force=True)
            data["status"] = "applied"
            data["applied_findings"] = sorted(approvals)
            data["changed_paths"] = changed
            _write(slug, data)
        except Exception:
            for path in reversed(changed):
                save_text(slug, path, originals[path])
                record_revision(slug, path, originals[path], source="editorial_batch_rollback",
                                note=f"Restored after failed editorial batch {plan_id}", force=True)
            data["status"] = "interrupted"
            _write(slug, data)
            raise
        # Refresh the quality assessment without hiding the successful edits.
        prior_run = get_editorial_run(slug, data["run_id"])
        try:
            refreshed = run_editorial(slug, EditorialRunRequest(
                scope=prior_run["scope"], path=prior_run["path"],
                reports=prior_run["reports"]))
            data["fresh_run_id"] = refreshed["id"]
        except (ValueError, OSError) as exc:
            data["refresh_error"] = str(exc)[:200]
        _write(slug, data)
        return data
