"""Part 4 — private publishing desk: source-backed readiness and release receipts.

No automatic distribution, uploads or publishing. Receipts represent an author's
record of review, never retailer approval or a guarantee of manuscript quality.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .distribution import list_release_artifacts, load_release_profile, validate_release
from .production_preflight import preflight
from .publishing import compiled_documents
from .storage import get_project, project_root

MAX_RECEIPTS = 100


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "publishing-desk-receipts.json"


def _receipts(slug: str) -> list[dict]:
    path = _path(slug)
    if not path.is_file():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or len(entries) > MAX_RECEIPTS:
        raise ValueError("Invalid publishing receipt archive")
    return entries


def _write_receipts(slug: str, entries: list[dict]) -> None:
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _compiled(slug: str) -> tuple[list[dict], str | None]:
    try:
        return compiled_documents(slug), None
    except (FileNotFoundError, ValueError, OSError) as exc:
        return [], str(exc)


def _fingerprint(documents: list[dict], profile: dict, artifacts: list) -> str:
    # Document ordering and exact content matter. A formatting or release
    # metadata change invalidates an earlier author's release review.
    payload = {
        "documents": [
            {
                "id": item["id"], "path": item["path"], "title": item["title"],
                "content_hash": hashlib.sha256(item["content"].encode("utf-8")).hexdigest(),
            } for item in documents
        ],
        "profile": profile,
        "release_assets": [
            {"path": item.relative_path, "hash": item.sha256, "bytes": item.bytes}
            for item in sorted(artifacts, key=lambda entry: entry.relative_path)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def report(slug: str) -> dict:
    project = get_project(slug)
    documents, compile_error = _compiled(slug)
    profile = load_release_profile(slug)
    profile_data = profile.model_dump(mode="json")
    artifact_records = list_release_artifacts(slug)
    valid = validate_release(slug, profile)
    editorial = preflight(slug)
    existing = _receipts(slug)
    source = _fingerprint(documents, profile_data, artifact_records)
    current_receipts = [item for item in existing if item.get("fingerprint") == source]
    formats = {"epub": False, "docx": False, "pdf": False}
    for item in artifact_records:
        suffix = item.suffix.lstrip(".")
        if suffix in formats:
            formats[suffix] = True
    stages = [
        {
            "id": "readiness", "title": "Manuscript check",
            "detail": "Editorial decisions, unfinished scenes, promises, and compile selection",
            "status": "needs_attention" if editorial["blockers"] or editorial["warnings"] else "reviewed",
            "count": editorial["blockers"] + editorial["warnings"],
        },
        {
            "id": "interior", "title": "Book interiors",
            "detail": "Binder sequence, previews, and generated EPUB / DOCX / PDF files",
            "status": "needs_attention" if compile_error or not any(formats.values()) else "reviewed",
            "count": len(documents),
        },
        {
            "id": "cover", "title": "Cover and identity",
            "detail": "Cover assets and complete public release metadata",
            "status": "needs_attention" if not profile.author or not any(a.role == "cover" for a in artifact_records)
                     else "reviewed",
            "count": sum(a.role == "cover" for a in artifact_records),
        },
        {
            "id": "audio", "title": "Narration",
            "detail": "Optional offline audiobook production",
            "status": "optional",
            "count": 0,
        },
        {
            "id": "distribution", "title": "Release packages",
            "detail": "Local retailer validations, submission material, and explicit package build",
            "status": "needs_attention" if not valid.valid else "reviewed",
            "count": len(valid.issues),
        },
        {
            "id": "history", "title": "Recovery",
            "detail": "Author checkpoints, previous exports, and release-review receipts",
            "status": "reviewed" if existing else "not_started",
            "count": len(existing),
        },
    ]
    return {
        "project_name": project["name"],
        "source_fingerprint": source,
        "chapter_count": len(documents),
        "words": sum(len(re.findall(r"\b[\w'-]+\b", item["content"])) for item in documents),
        "compile_error": compile_error,
        "chapters": [
            {
                "id": item["id"], "title": item["title"], "path": item["path"],
                "words": len(item["content"].split()),
            } for item in documents
        ][:150],
        "formats": formats,
        "files": [
            {
                "filename": item.filename, "relative_path": item.relative_path,
                "suffix": item.suffix, "bytes": item.bytes, "role": item.role,
                "sha256": item.sha256, "modified_at": item.modified_at,
            } for item in artifact_records[:80]
        ],
        "editorial": {
            "blockers": editorial["blockers"], "warnings": editorial["warnings"],
            "waived": editorial["waived"],
            "issues": editorial["issues"][:60],
            "disclaimer": editorial["disclaimer"],
        },
        "distribution": {
            "valid": valid.valid, "issues": [issue.model_dump(mode="json") for issue in valid.issues[:60]],
            "enabled_editions": valid.enabled_editions,
            "retailers": valid.selected_retailers,
        },
        "profile": {
            "title": profile.title, "author": profile.author, "description": profile.description,
            "publisher": profile.publisher, "language": profile.language,
            "editions": [
                {"id": e.id, "format": e.format, "enabled": e.enabled,
                 "retailers": e.retailers, "interior_path": e.interior_path,
                 "cover_path": e.cover_path} for e in profile.editions
            ],
        },
        "stages": stages,
        "receipts": [{
            **item, "current": item.get("fingerprint") == source,
        } for item in existing[:30]],
        "reviewed_current": bool(current_receipts),
        "privacy": "No manuscript is uploaded, distributed or published by this publishing desk.",
        "artifact_fingerprint_included": True,
        "limitations": "Local checks are advisory. EPUB container, DOCX, PDF and retailer validation "
                       "are not a guarantee of accessibility, production acceptance, legal clearance "
                       "or commercial readiness. Artifacts can predate current chapters.",
    }


def signoff(slug: str, fingerprint: str, note: str, acknowledged: bool) -> dict:
    if not acknowledged:
        raise ValueError("Explicit author acknowledgment is required")
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise ValueError("Invalid manuscript and release fingerprint")
    note = note.strip()
    if not 12 <= len(note) <= 1200:
        raise ValueError("Please record a specific review note of 12–1200 characters")
    snapshot = report(slug)
    if fingerprint != snapshot["source_fingerprint"]:
        raise ValueError("The manuscript or release metadata changed since review. Rescan before signing.")
    entries = _receipts(slug)
    if len(entries) >= MAX_RECEIPTS:
        raise ValueError("Receipt history is full")
    receipt = {
        "id": uuid4().hex,
        "created_at": _now(),
        "fingerprint": fingerprint,
        "note": note,
        "chapter_count": snapshot["chapter_count"],
        "words": snapshot["words"],
        "editorial_blockers": snapshot["editorial"]["blockers"],
        "editorial_warnings": snapshot["editorial"]["warnings"],
        "distribution_valid": snapshot["distribution"]["valid"],
        "format_snapshot": snapshot["formats"],
        "type": "author_review_receipt",
        "local_only": True,
    }
    _write_receipts(slug, [receipt, *entries])
    return receipt
