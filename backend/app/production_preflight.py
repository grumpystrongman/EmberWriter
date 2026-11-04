"""Evidence-backed, author-owned release checklist.

A quality preflight, not retailer certification. It does not modify manuscripts,
approve prose or prohibit exports. It never consumes third-party APIs.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .book_studio import load_state
from .canon_ripple import list_ripples
from .distribution import load_release_profile
from .manuscript_intelligence import _chapters, list_promises
from .publishing import compiled_documents
from .quality_clinic import check_text
from .style_bible import audit as style_audit
from .prose_editor import analyze as prose_scan
from .editorial_board import freshness as editorial_freshness
from .storage import get_project, project_root

MAX_WAIVERS = 300
MAX_MANUSCRIPT_BYTES = 12_000_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "release-preflight.json"


def _load(slug: str) -> list[dict]:
    path = _path(slug)
    if not path.exists():
        return []
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, list) or len(content) > MAX_WAIVERS:
        raise ValueError("Invalid release preflight decisions")
    return content


def _save(slug: str, records: list[dict]):
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def preflight(slug: str) -> dict:
    get_project(slug)
    issues = []

    def add(level: str, code: str, title: str, detail: str,
            path: str = "", evidence: str = "", version: str = ""):
        # Source-version-aware: waived issues reappear after the underlying prose
        # changes, so a waiver never silently covers a new manuscript.
        signature = _hash("|".join([code, path, evidence, version]))
        issues.append({
            "id": signature, "level": level, "code": code, "title": title,
            "detail": detail, "path": path, "evidence": evidence[:210],
            "waivable": level != "blocker", "waived": False, "waiver_reason": "",
        })

    chapters = _chapters(slug)
    total_bytes = sum(len(ch["text"].encode("utf-8")) for ch in chapters)
    if total_bytes > MAX_MANUSCRIPT_BYTES:
        raise ValueError("Release preflight supports up to 12 MB of chapter text")
    total_words = sum(len(ch["text"].split()) for ch in chapters)
    if not chapters:
        add("blocker", "no_manuscript", "No substantial manuscript content",
            "Create or import manuscript chapters before preparing an edition.")
    elif total_words < 500:
        add("warning", "very_short", "Manuscript is unusually short",
            f"Current chapter text totals {total_words} words. Confirm the intended format and length.",
            version=_hash(str(total_words)))
    if len(chapters) > 100:
        add("warning", "many_documents", "Large manuscript",
            "Check chapter sequencing, consistent formatting, and export performance.")

    state = load_state(slug)
    if state.get("configured"):
        planned = state.get("chapters", [])
        unapproved = [ch for ch in planned if ch.get("status") != "approved"]
        undrafted = [ch for ch in planned if ch.get("status") in ("planned", "failed", "generating")]
        if undrafted:
            add("warning", "unfinished_plan", "Chapter plan is incomplete",
                f"{len(undrafted)} of {len(planned)} chapters still await complete drafts.",
                version=_hash(json.dumps([(ch["number"], ch["status"]) for ch in undrafted])))
        if unapproved:
            add("warning", "unapproved_chapters", "Chapter candidates await author approval",
                f"{len(unapproved)} planned chapters are not yet approved for the manuscript.",
                version=_hash(json.dumps([(ch["number"], ch["status"]) for ch in unapproved])))

    for promise in list_promises(slug):
        if promise.get("status") == "open":
            add("warning", "open_story_promise", "Unresolved author-tracked story promise",
                promise.get("title", "An unresolved plot promise")[:200],
                evidence=promise.get("tracking_phrase", ""),
                version=promise.get("id", ""))
    for change in list_ripples(slug):
        if change.get("status") in ("proposed", "approved"):
            pending = sum(match.get("review_status") != "reviewed" for match in change.get("matches", []))
            add("warning", "canon_change", "Canon change still needs review",
                f"{change.get('title', 'Proposed canon change')}; {pending} document(s) still await review.",
                path=change.get("source_path", ""),
                version=_hash(json.dumps([change.get("id"), change.get("status"),
                                          [(m.get("path"), m.get("review_status")) for m in change.get("matches", [])]])))

    for ch in chapters:
        content = ch["text"]
        fingerprint = _hash(content)
        if len(content.split()) < 40:
            add("warning", "short_chapter", "Chapter may be incomplete",
                f"{ch['title']} contains fewer than 40 words.",
                path=ch["path"], version=fingerprint)
        lines = content.splitlines()
        for index, line in enumerate(lines, 1):
            if re.search(r"\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b", line, flags=re.I):
                add("warning", "editorial_marker", "Unresolved editorial marker",
                    f"Found a possible drafting placeholder on line {index}.",
                    path=ch["path"], evidence=line.strip()[:190], version=fingerprint)
                break
        mechanical = check_text(content)
        likely = [f for f in mechanical["findings"] if f.get("severity") == "likely_error"]
        if likely:
            add("warning", "proofreading", "Potential proofreading errors",
                f"{len(likely)} likely typo(s) or repeated words in {ch['title']}.",
                path=ch["path"], evidence=likely[0]["excerpt"], version=fingerprint)

    try:
        selected = compiled_documents(slug)
        selected_paths = {doc["path"] for doc in selected}
        if not selected:
            add("blocker", "compile_empty", "The publishing binder contains no selected chapters",
                "Select the intended manuscript documents in the Binder.")
        else:
            if any(ch["path"].startswith("manuscript/") and ch["path"] not in selected_paths for ch in chapters):
                add("warning", "compile_coverage", "Some manuscript chapters are excluded from Compile",
                    "Review the Binder's Draft selection and ordering before exporting.",
                    version=_hash("|".join(sorted(selected_paths))))
    except (ValueError, FileNotFoundError):
        add("blocker", "compile_empty", "No Draft documents are enabled for Compile",
            "Include the intended manuscript chapters in the Draft binder.")

    for ch in chapters:
        inspected = prose_scan(slug, ch["path"])
        likely = [f for f in inspected["findings"] if f["rule"] in ("modal_of", "double_word")
                  and f["decision"] == "pending"]
        if likely:
            add("warning", "prose_editor", "Potential grammar mistakes await review",
                f"{len(likely)} high-confidence mechanical correction(s) in {ch['title']} need author inspection.",
                path=ch["path"], evidence=likely[0]["excerpt"],
                version=inspected["source_hash"])

    style = style_audit(slug)
    if style["outstanding"]:
        add("warning", "style_bible", "Style Bible terminology needs review",
            f"{style['outstanding']} terminology occurrence(s) still await author review across {style['chapters']} chapter(s)." +
            (" Findings were truncated at the scan limit." if style["truncated"] else ""),
            version=_hash("|".join(item["id"] for item in style["findings"] if not item["dismissed"])))

    editorial = editorial_freshness(slug)
    if editorial["scanned"] and not editorial["current"]:
        add("warning", "stale_editorial_scan", "Whole-book editorial review is outdated",
            f"{len(editorial['changed'])} manuscript chapter(s) changed since the last saved editorial scan. Rerun Plan > Editorial Board before publication.",
            version=editorial["change_signature"])

    profile = load_release_profile(slug)
    if not profile.author.strip():
        add("warning", "missing_author", "Publication author or pen name is missing",
            "Set the author/pen name in your release profile.")
    if not profile.description.strip():
        add("warning", "missing_description", "Book description is missing",
            "Prepare a retail description before submitting to retailers.")
    if not profile.editions:
        add("warning", "no_editions", "No retailer editions configured",
            "Configure at least one intended edition before distributing.")

    waivers = {item.get("id"): item for item in _load(slug)}
    for issue in issues:
        if issue["waivable"] and issue["id"] in waivers:
            record = waivers[issue["id"]]
            if record.get("reason", "").strip():
                issue["waived"] = True
                issue["waiver_reason"] = record["reason"][:1200]

    blocking = sum(issue["level"] == "blocker" for issue in issues)
    remaining = sum(not issue["waived"] and issue["level"] == "warning" for issue in issues)
    return {
        "project": slug, "words": total_words, "chapter_count": len(chapters),
        "issues": issues, "blockers": blocking, "warnings": remaining,
        "waived": sum(item["waived"] for item in issues),
        "editorially_ready": blocking == 0 and remaining == 0,
        "disclaimer": (
            "Advisory checklist only. An editorially ready result does not guarantee "
            "literary quality, professional proofreading, legal clearance, accessibility, "
            "retailer acceptance or print-file correctness. Exports remain author-controlled."
        ),
    }


def waive(slug: str, issue_id: str, reason: str) -> dict:
    if not 12 <= len(reason.strip()) <= 1200:
        raise ValueError("Provide a specific 12–1200 character reason for waiving this warning")
    report = preflight(slug)
    issue = next((item for item in report["issues"] if item["id"] == issue_id), None)
    if issue is None:
        raise FileNotFoundError("Preflight issue is no longer present")
    if not issue["waivable"]:
        raise ValueError("Release blockers cannot be waived")
    records = _load(slug)
    if len(records) >= MAX_WAIVERS and not any(r.get("id") == issue_id for r in records):
        raise ValueError("Waiver history is full")
    records = [record for record in records if record.get("id") != issue_id]
    records.append({"id": issue_id, "reason": reason.strip(), "created_at": _now()})
    _save(slug, records)
    return preflight(slug)


def restore(slug: str, issue_id: str) -> dict:
    records = _load(slug)
    if not any(record.get("id") == issue_id for record in records):
        raise FileNotFoundError("Waiver not found")
    _save(slug, [record for record in records if record.get("id") != issue_id])
    return preflight(slug)


def markdown(slug: str) -> str:
    report = preflight(slug)
    lines = [
        "# EmberWriter Production Preflight",
        "",
        f"Chapters: {report['chapter_count']}; words: {report['words']}.",
        f"Blocking concerns: {report['blockers']}; outstanding warnings: {report['warnings']}; waived: {report['waived']}.",
        "",
        "> " + report["disclaimer"],
        "",
    ]
    for issue in report["issues"]:
        lines.extend([
            f"## {issue['title']} [{issue['level'].upper()}]",
            issue["detail"],
            f"Source: {issue['path']}" if issue["path"] else "",
            f"Evidence: {issue['evidence']}" if issue["evidence"] else "",
            f"Waiver: {issue['waiver_reason']}" if issue["waived"] else "",
            "",
        ])
    return "\n".join(lines)
