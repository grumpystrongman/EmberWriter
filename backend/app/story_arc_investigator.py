"""Evidence-first local narrative analysis across a book.

The author chooses each chapter to examine. The engine validates every
narrative claim against an exact quote in that chapter. No source prose is
changed, and model judgments remain explicitly subjective. Other projects
are never consulted.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .book_studio import _local_model
from .generation import generate
from .manuscript_intelligence import _chapters, create_promise
from .models import ProviderConfig
from .storage import get_project, project_root

CATEGORIES = {"choice", "consequence", "relationship", "revelation", "foreshadowing", "conflict", "change"}
MAX_CHARS = 85_000
MAX_EVIDENCE = 12
_LOCKS: dict[str, asyncio.Lock] = {}


def _stamp() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "story-arcs.json"


def _load(slug: str) -> dict:
    path = _path(slug)
    if not path.exists():
        return {"analyses": []}
    content = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(content, dict) or not isinstance(content.get("analyses"), list):
        raise ValueError("Story arc ledger is invalid")
    return content


def _save(slug: str, data: dict):
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _available(slug: str) -> list[dict]:
    return _chapters(slug)


def chapters(slug: str) -> list[dict]:
    return [{"path": ch["path"], "title": ch["title"], "status": ch["status"],
             "words": len(ch["text"].split()), "fingerprint": _hash(ch["text"])[:16]}
            for ch in _available(slug)]


def overview(slug: str) -> dict:
    sources = {ch["path"]: _hash(ch["text"]) for ch in _available(slug)}
    data = _load(slug)
    for record in data["analyses"]:
        record["stale"] = sources.get(record.get("path")) != record.get("source_hash")
    rows = [
        {
            "path": ch["path"], "title": ch["title"],
            "status": ch["status"], "words": len(ch["text"].split()),
            "analysis": next(
                (r for r in data["analyses"] if r.get("path") == ch["path"] and not r["stale"]),
                None,
            ),
        }
        for ch in _available(slug)
    ]
    return {
        "chapters": rows,
        "analyzed": sum(bool(row["analysis"]) for row in rows),
        "total": len(rows),
        "review_required": sum(
            1 for row in rows for event in (row["analysis"] or {}).get("events", [])
            if event.get("decision") == "pending"
        ),
        "historical_analyses": data["analyses"],
        "limitations": (
            "Evidence is grounded in exact text; category labels and tension ratings "
            "are subjective local model interpretations, not objective story truth."
        ),
    }


def _decode(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^" + re.escape("```") + r"(?:json)?\s*|\s*" + re.escape("```") + "$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("The local model did not return structured JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid narrative assessment")
    return data


def _events(raw: object, source: str) -> tuple[list[dict], int]:
    if not isinstance(raw, list) or len(raw) > MAX_EVIDENCE:
        raise ValueError("Narrative assessment has too many events")
    verified = []
    for event in raw:
        if not isinstance(event, dict):
            continue
        quote = str(event.get("quote", "")).strip()
        kind = str(event.get("kind", "")).strip()
        label = str(event.get("label", "")).strip()
        meaning = str(event.get("meaning", "")).strip()
        subject = str(event.get("subject", "")).strip()
        if (kind not in CATEGORIES or not 8 <= len(quote) <= 280
                or quote not in source or not label or len(label) > 130
                or not meaning or len(meaning) > 650 or len(subject) > 100):
            continue
        offset = source.index(quote)
        verified.append({
            "id": uuid4().hex, "kind": kind, "label": label,
            "subject": subject, "meaning": meaning,
            "quote": quote, "line": source.count("\n", 0, offset) + 1,
            "decision": "pending",
            "promoted_promise_id": None,
        })
    return verified, len(raw) - len(verified)


async def inspect(slug: str, path: str, config: ProviderConfig, focus: str = "") -> dict:
    _local_model(config)
    if len(focus) > 1000:
        raise ValueError("Focus is too long")
    lock = _LOCKS.setdefault(slug, asyncio.Lock())
    if lock.locked():
        raise ValueError("A chapter is already being analyzed in this project")
    async with lock:
        source = next((ch for ch in _available(slug) if ch["path"] == path), None)
        if source is None:
            raise FileNotFoundError("Chapter is not present in the selected project")
        content = source["text"]
        if not 30 <= len(content.split()) or len(content) > MAX_CHARS:
            raise ValueError("Narrative review requires 30+ words and no more than 85,000 characters per chapter")
        expected_hash = _hash(content)
        prior = next((ch for ch in _available(slug) if ch["path"] == path), None)
        if prior is None:
            raise FileNotFoundError("Chapter not found")
        prompt = (
            "You are examining ONE chapter of fiction and must not infer events from "
            "other chapters. Label each concrete on-page decision, consequence, "
            "relationship shift, conflict turn, revelation, change, or possible foreshadowing. "
            "Use exact short quotations that appear VERBATIM in the supplied chapter. "
            "Never assume that mentioning an object proves foreshadowing. "
            "A future plot payoff is only a hypothesis. Do not invent character facts. "
            "Return JSON only: {\"summary\":\"...\",\"tension\":3,"
            "\"events\":[{\"kind\":\"choice\",\"label\":\"...\","
            "\"subject\":\"character or plot thread\",\"quote\":\"exact text\","
            "\"meaning\":\"why this event could matter\"}]}. "
            "Tension is an explicitly subjective 1-5 scale; include up to 10 events. "
            "Focus: " + (focus or "story causality and promises") +
            "\n\nCHAPTER " + source["title"] + ":\n" + content
        )
        result = await generate(
            config,
            [{"role": "system", "content": "You are a meticulous, constructive literary analyst. Claims need exact textual evidence. Return JSON only."},
             {"role": "user", "content": prompt}],
            json_mode=True, temperature=0.3, max_output_tokens=3800,
        )
        parsed = _decode(result)
        if _hash(next((ch["text"] for ch in _available(slug) if ch["path"] == path), "")) != expected_hash:
            raise ValueError("Author edited this chapter during analysis; discard and rescan")
        summary = str(parsed.get("summary", "")).strip()
        tension = parsed.get("tension")
        if not summary or len(summary) > 1000 or type(tension) is not int or tension not in range(1, 6):
            raise ValueError("Narrative assessment is incomplete")
        events, rejected = _events(parsed.get("events", []), content)
        record = {
            "id": uuid4().hex, "path": path, "title": source["title"],
            "source_hash": expected_hash, "model": config.model,
            "created_at": _stamp(), "summary": summary,
            "tension": tension, "events": events,
            "unverified_events_rejected": rejected, "stale": False,
        }
        data = _load(slug)
        # One current analysis per chapter; retain prior version for audit.
        data["analyses"] = [record, *data["analyses"]][:200]
        _save(slug, data)
        return record


def act(slug: str, analysis_id: str, event_id: str, action: str) -> dict:
    if action not in ("accept", "dismiss", "reopen", "track_promise"):
        raise ValueError("Unsupported arc action")
    data = overview(slug)
    record = next((a for a in data["historical_analyses"] if a.get("id") == analysis_id), None)
    if record is None:
        raise FileNotFoundError("Arc analysis was not found")
    if record["stale"]:
        raise ValueError("This analysis describes an older draft")
    event = next((e for e in record["events"] if e.get("id") == event_id), None)
    if event is None:
        raise FileNotFoundError("Arc event was not found")
    if action == "track_promise":
        if event["kind"] != "foreshadowing":
            raise ValueError("Only foreshadowing hypotheses can become tracked promises")
        if event.get("promoted_promise_id"):
            raise ValueError("This event is already in the promise ledger")
        # A tracking phrase must be 3-150 chars; use verified evidence.
        phrase = event["quote"][:150]
        promise = create_promise(
            slug, title=event["label"], tracking_phrase=phrase,
            intention=f"Author-confirmed story-arc hypothesis: {event['meaning'][:650]}",
        )
        event["decision"] = "accepted"
        event["promoted_promise_id"] = promise["id"]
    else:
        event["decision"] = {"accept": "accepted", "dismiss": "dismissed", "reopen": "pending"}[action]
    current = _load(slug)
    # Synchronize by stable IDs rather than persisting stale-cache mutations.
    for item in current["analyses"]:
        if item["id"] == analysis_id:
            for target in item["events"]:
                if target["id"] == event_id:
                    target.update(event)
    _save(slug, current)
    return event


def dossier(slug: str) -> dict:
    """Deterministic cross-chapter rollup of verified *current* arc assessments."""
    board = overview(slug)
    rows = []
    trajectories: dict[str, list[dict]] = {}
    unanswered = []
    for order, chapter in enumerate(board["chapters"], 1):
        assessment = chapter["analysis"]
        if not assessment:
            rows.append({
                "index": order, "title": chapter["title"], "path": chapter["path"],
                "analyzed": False, "tension": None, "summary": "",
                "accepted": [], "pending_count": 0,
            })
            continue
        accepted = [event for event in assessment["events"] if event["decision"] == "accepted"]
        pending = [event for event in assessment["events"] if event["decision"] == "pending"]
        for event in accepted:
            key = event["subject"].strip() or "General plot"
            trajectories.setdefault(key, []).append({
                "chapter": order, "title": chapter["title"], "kind": event["kind"],
                "label": event["label"], "quote": event["quote"], "path": chapter["path"],
            })
        for event in assessment["events"]:
            if event["kind"] == "foreshadowing" and not event.get("promoted_promise_id") and event["decision"] != "dismissed":
                unanswered.append({
                    "chapter": order, "title": chapter["title"], "quote": event["quote"],
                    "label": event["label"], "decision": event["decision"], "path": chapter["path"],
                })
        rows.append({
            "index": order, "title": chapter["title"], "path": chapter["path"],
            "analyzed": True, "tension": assessment["tension"],
            "summary": assessment["summary"], "accepted": accepted,
            "pending_count": len(pending),
        })
    return {
        "chapters": rows,
        "trajectories": [
            {"subject": subject, "events": events} for subject, events in sorted(trajectories.items())
        ],
        "untracked_foreshadowing": unanswered,
        "analyzed": board["analyzed"], "total": board["total"],
        "review_required": board["review_required"],
        "method": (
            "Deterministic rollup from individually verified, current chapter analyses. "
            "Character trajectories include accepted interpretations only. Unreviewed "
            "foreshadowing is shown separately as a hypothesis, not an unresolved fact."
        ),
    }


def dossier_markdown(slug: str) -> str:
    report = dossier(slug)
    lines = [
        "# Story Arc Dossier",
        "",
        f"Chapters assessed: {report['analyzed']} of {report['total']}; "
        f"observations pending author review: {report['review_required']}.",
        "",
        "> " + report["method"],
        "",
        "## Chapter trajectory",
    ]
    for ch in report["chapters"]:
        lines.extend([
            "",
            f"### {ch['index']}. {ch['title']}",
            f"Source: {ch['path']}",
            f"Perceived tension: {ch['tension']}/5" if ch["analyzed"] else "Not yet analyzed.",
        ])
        if ch["analyzed"]:
            lines.append(ch["summary"])
            lines.append(f"Accepted evidence: {len(ch['accepted'])}; pending observations: {ch['pending_count']}.")
            for event in ch["accepted"]:
                lines.append(f"- {event['kind']}: {event['label']} — \"{event['quote']}\"")
    lines.extend(["", "## Subject trajectories"])
    if not report["trajectories"]:
        lines.append("No author-accepted character/subject events yet.")
    for subject in report["trajectories"]:
        lines.extend(["", f"### {subject['subject']}"])
        for item in subject["events"]:
            lines.append(
                f"- Chapter {item['chapter']}, {item['kind']}: {item['label']} "
                f"(evidence: \"{item['quote']}\")"
            )
    lines.extend(["", "## Untracked possible story promises"])
    if not report["untracked_foreshadowing"]:
        lines.append("No current untracked foreshadowing hypotheses.")
    for item in report["untracked_foreshadowing"]:
        lines.append(
            f"- Chapter {item['chapter']}: {item['label']} "
            f"[{item['decision']}] — \"{item['quote']}\""
        )
    lines.append("")
    return "\n".join(lines)
