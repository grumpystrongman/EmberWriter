from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from typing import Any
from uuid import uuid4

from .editorial import (
    analyze_text,
    get_editorial_profile,
    report_catalog,
    update_finding_status,
)
from .editorial_models import (
    EditorialFixApplyRequest,
    EditorialFixApplyResult,
    EditorialFixProposal,
    EditorialFixRequest,
)
from .generation import generate
from .revisions import record_revision
from .storage import project_root, read_text, save_text, utc_now

_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+[\"'’”)]*|$)", re.MULTILINE)
_PARAGRAPH_REPORTS = {"paragraph_length"}
_STYLE_PATHS = (
    "style/voice-profile.json",
    "style/author-profile.md",
    "style/craft-profile.json",
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_finding(slug: str, finding_id: str) -> dict[str, Any]:
    db_path = project_root(slug) / ".ember" / "story.db"
    if not db_path.exists():
        raise FileNotFoundError(finding_id)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM editorial_findings WHERE id = ?",
            (finding_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise FileNotFoundError(finding_id)
    finding = dict(row)
    definitions = {item["id"]: item for item in report_catalog()}
    definition = definitions.get(finding["report_id"], {})
    finding["report_name"] = definition.get("name", finding["report_id"])
    finding["category"] = definition.get("category", "style")
    return finding


def _paragraph_span(source: str, start: int, end: int) -> tuple[int, int]:
    left = source.rfind("\n\n", 0, max(0, start))
    left = 0 if left < 0 else left + 2
    right = source.find("\n\n", max(end, start))
    right = len(source) if right < 0 else right
    while left < right and source[left].isspace():
        left += 1
    while right > left and source[right - 1].isspace():
        right -= 1
    return left, right


def _target_span(source: str, finding: dict[str, Any]) -> tuple[int, int]:
    start = max(0, min(int(finding["start_offset"]), len(source)))
    end = max(start, min(int(finding["end_offset"]), len(source)))
    if finding["report_id"] in _PARAGRAPH_REPORTS:
        return _paragraph_span(source, start, end)

    paragraph_start, paragraph_end = _paragraph_span(source, start, end)
    paragraph = source[paragraph_start:paragraph_end]
    relative = start - paragraph_start
    for match in _SENTENCE_RE.finditer(paragraph):
        if match.start() <= relative <= match.end():
            target_start = paragraph_start + match.start()
            target_end = paragraph_start + match.end()
            while target_start < target_end and source[target_start].isspace():
                target_start += 1
            while target_end > target_start and source[target_end - 1].isspace():
                target_end -= 1
            if target_end > target_start:
                return target_start, target_end

    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    if line_end < 0:
        line_end = len(source)
    return line_start, line_end


def _style_context(slug: str) -> str:
    sections: list[str] = []
    for path in _STYLE_PATHS:
        try:
            content = read_text(slug, path).strip()
        except (FileNotFoundError, OSError, UnicodeError, ValueError):
            continue
        if content:
            sections.append(f"[{path}]\n{content[:4000]}")
    return "\n\n".join(sections)


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TypeError("Editorial fix model response must be a JSON object")
    return value


def _decision_key(item: sqlite3.Row | dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item["anchor_text"]).strip().casefold(),
        str(item["message"]).strip(),
        str(item["excerpt"]).strip(),
    )


def _refresh_applied_report(slug: str, finding: dict[str, Any]) -> None:
    """Replace stale open findings for this report/document with fresh analysis.

    Resolved and ignored findings remain as durable editorial decisions. If the exact
    same finding still appears after the edit, it is not re-added as open.
    """
    source = read_text(slug, finding["path"])
    source_hash = _hash(source)
    profile = get_editorial_profile(slug)
    fresh_findings, _ = analyze_text(source, [finding["report_id"]], profile)
    created_at = utc_now()

    db_path = project_root(slug) / ".ember" / "story.db"
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        existing = con.execute(
            """
            SELECT * FROM editorial_findings
            WHERE run_id = ? AND path = ? AND report_id = ?
            """,
            (finding["run_id"], finding["path"], finding["report_id"]),
        ).fetchall()
        reviewed_keys = {
            _decision_key(row)
            for row in existing
            if row["status"] in {"resolved", "ignored"}
        }

        con.execute(
            """
            DELETE FROM editorial_findings
            WHERE run_id = ? AND path = ? AND report_id = ? AND status = 'open'
            """,
            (finding["run_id"], finding["path"], finding["report_id"]),
        )

        rows = []
        for item in fresh_findings:
            if _decision_key(item) in reviewed_keys:
                continue
            rows.append(
                (
                    uuid4().hex,
                    finding["run_id"],
                    item["report_id"],
                    item["severity"],
                    "open",
                    finding["path"],
                    finding.get("binder_node_id"),
                    item["start_offset"],
                    item["end_offset"],
                    item["line"],
                    item["excerpt"],
                    item["anchor_text"],
                    item["message"],
                    item["suggestion"],
                    source_hash,
                    created_at,
                )
            )
        if rows:
            con.executemany(
                """
                INSERT INTO editorial_findings
                (id, run_id, report_id, severity, status, path, binder_node_id, start_offset,
                 end_offset, line, excerpt, anchor_text, message, suggestion, source_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        run_row = con.execute(
            "SELECT summary_json FROM editorial_runs WHERE id = ?",
            (finding["run_id"],),
        ).fetchone()
        if run_row is None:
            raise FileNotFoundError(finding["run_id"])
        all_rows = con.execute(
            "SELECT report_id, severity FROM editorial_findings WHERE run_id = ?",
            (finding["run_id"],),
        ).fetchall()
        summary = json.loads(run_row["summary_json"])
        summary["by_report"] = dict(Counter(row["report_id"] for row in all_rows))
        summary["by_severity"] = dict(Counter(row["severity"] for row in all_rows))
        con.execute(
            "UPDATE editorial_runs SET findings = ?, summary_json = ? WHERE id = ?",
            (len(all_rows), json.dumps(summary), finding["run_id"]),
        )


async def propose_editorial_fix(slug: str, request: EditorialFixRequest) -> EditorialFixProposal:
    finding = _load_finding(slug, request.finding_id)
    source = read_text(slug, finding["path"])
    source_hash = _hash(source)
    if source_hash != finding["source_hash"]:
        raise ValueError("This finding is stale because the manuscript changed. Rerun Editorial Studio before applying an AI fix.")

    target_start, target_end = _target_span(source, finding)
    original = source[target_start:target_end]
    if not original.strip():
        raise ValueError("Could not resolve editable prose for this finding")

    context_start = max(0, target_start - 1200)
    context_end = min(len(source), target_end + 1200)
    surrounding = source[context_start:context_end]
    style = _style_context(slug)
    instruction = request.instruction.strip()

    system = """You are EmberWriter's precise fiction line editor.
Return ONLY a JSON object with keys: replacement, rationale.

Edit only the ORIGINAL PASSAGE. Preserve established story facts, POV, tense, character voice, formatting intent, and the author's stylistic identity. The editorial report is a signal to inspect, not a command to flatten the prose. If the flagged construction is intentional or the best choice, return the original passage unchanged and explain why briefly.

When a change helps, solve the underlying prose problem rather than mechanically deleting a flagged word. For example, an adverb may call for a stronger verb, sharper action, better dialogue beat, or no change at all. Do not introduce new plot facts, names, motivations, sensory facts, or character knowledge. Do not rewrite surrounding material that is outside ORIGINAL PASSAGE. Preserve Markdown markers when they are part of the passage.
"""
    user = f"""EDITORIAL FINDING
Report: {finding['report_name']} ({finding['report_id']})
Message: {finding['message']}
Existing suggestion: {finding['suggestion']}
Flagged anchor: {finding['anchor_text']}
Author instruction: {instruction or '(none)'}

ORIGINAL PASSAGE
<<<
{original}
>>>

SURROUNDING MANUSCRIPT CONTEXT
<<<
{surrounding}
>>>

AUTHOR / BOOK STYLE CONTEXT
{style or '(No explicit style profile is available. Preserve the voice visible in the manuscript context.)'}
"""

    raw = await generate(
        request.provider,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.35,
        top_p=0.9,
        json_mode=True,
    )
    payload = _parse_json_object(raw)
    replacement = payload.get("replacement")
    rationale = payload.get("rationale")
    if not isinstance(replacement, str):
        raise TypeError("Editorial fix response did not contain replacement text")
    if not isinstance(rationale, str):
        rationale = "AI line-edit proposal"
    if len(replacement) > max(4000, len(original) * 5):
        raise ValueError("Editorial fix proposal was unexpectedly large; no change was applied")

    return EditorialFixProposal(
        finding_id=request.finding_id,
        path=finding["path"],
        report_id=finding["report_id"],
        report_name=finding["report_name"],
        original=original,
        replacement=replacement,
        rationale=rationale.strip() or "AI line-edit proposal",
        source_hash=source_hash,
        target_start=target_start,
        target_end=target_end,
        changed=replacement != original,
    )


def apply_editorial_fix(slug: str, request: EditorialFixApplyRequest) -> EditorialFixApplyResult:
    finding = _load_finding(slug, request.finding_id)
    if finding["status"] != "open":
        raise ValueError("This editorial finding is no longer open")
    if finding["path"] != request.path:
        raise ValueError("Editorial fix path does not match the finding")

    source = read_text(slug, finding["path"])
    current_hash = _hash(source)
    if current_hash != finding["source_hash"] or current_hash != request.source_hash:
        raise ValueError("This finding is stale because the manuscript changed. Rerun Editorial Studio before applying the fix.")

    expected_start, expected_end = _target_span(source, finding)
    if (request.target_start, request.target_end) != (expected_start, expected_end):
        raise ValueError("Editorial fix target no longer matches the analyzed passage")
    if request.target_end > len(source) or request.target_start > request.target_end:
        raise ValueError("Editorial fix target is outside the manuscript")

    original = source[request.target_start:request.target_end]
    if original != request.original:
        raise ValueError("Editorial fix source passage changed before apply")
    if request.replacement == request.original:
        raise ValueError("The proposal does not change the manuscript")

    updated = source[:request.target_start] + request.replacement + source[request.target_end:]
    note = f"{finding['report_name']} AI fix"
    if request.rationale.strip():
        note = f"{note}: {request.rationale.strip()[:500]}"

    save_text(slug, request.path, updated)
    try:
        revision = record_revision(
            slug,
            request.path,
            updated,
            source="editorial_fix",
            note=note,
            force=True,
        )
        resolved = update_finding_status(slug, request.finding_id, "resolved")
        _refresh_applied_report(slug, finding)
    except Exception:
        try:
            update_finding_status(slug, request.finding_id, "open")
        except (FileNotFoundError, ValueError):
            pass
        save_text(slug, request.path, source)
        record_revision(
            slug,
            request.path,
            source,
            source="editorial_fix_rollback",
            note="Automatic rollback after editorial fix apply failure",
            force=True,
        )
        raise

    return EditorialFixApplyResult(
        path=request.path,
        content=updated,
        finding=resolved,
        revision=revision,
    )
