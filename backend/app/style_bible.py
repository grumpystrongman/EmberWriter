"""Author-owned local style bible and terminology review.

A deterministic search of current manuscript chapters; no cloud calls,
no model judgments, and no unapproved text modifications. Every finding
has a literal excerpt, source fingerprint, and dismiss/reopen state.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .manuscript_intelligence import _chapters
from .storage import get_project, project_root

MAX_RULES = 250
MAX_CHAPTERS = 120
MAX_BYTES = 12_000_000
MAX_FINDINGS = 2000
RULE_TYPES = {"preferred", "avoid", "watch"}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "style-bible.json"


def _load(slug: str) -> dict:
    path = _path(slug)
    if not path.exists():
        return {"rules": [], "dismissals": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list) or not isinstance(data.get("dismissals"), dict):
        raise ValueError("Style Bible is corrupt")
    if len(data["rules"]) > MAX_RULES or len(data["dismissals"]) > MAX_FINDINGS:
        raise ValueError("Style Bible exceeds its permitted size")
    return data


def _write(slug: str, state: dict) -> None:
    dest = _path(slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(dest)


def rules(slug: str) -> list[dict]:
    return _load(slug)["rules"]


def add(slug: str, category: str, phrase: str, preferred: str = "",
        note: str = "", case_sensitive: bool = False) -> dict:
    phrase, preferred, note = phrase.strip(), preferred.strip(), note.strip()
    if category not in RULE_TYPES or not 2 <= len(phrase) <= 120:
        raise ValueError("Choose a valid rule type and a 2–120 character phrase")
    if len(preferred) > 120 or len(note) > 500:
        raise ValueError("Preferred spelling or note is too long")
    if category == "preferred" and (len(preferred) < 2 or phrase.casefold() == preferred.casefold()):
        raise ValueError("Preferred spelling must differ from the flagged spelling")
    if category != "preferred" and preferred:
        raise ValueError("Only preferred-spelling rules accept a replacement")
    data = _load(slug)
    if len(data["rules"]) >= MAX_RULES:
        raise ValueError("Style Bible is full (250 rules)")
    if any(r.get("phrase", "").casefold() == phrase.casefold()
           and r.get("category") == category for r in data["rules"]):
        raise ValueError("This rule is already in the Style Bible")
    item = {
        "id": uuid4().hex, "category": category, "phrase": phrase,
        "preferred": preferred, "note": note,
        "case_sensitive": bool(case_sensitive), "created_at": _now(),
    }
    data["rules"].append(item)
    _write(slug, data)
    return item


def delete(slug: str, rule_id: str) -> dict:
    data = _load(slug)
    if not any(rule.get("id") == rule_id for rule in data["rules"]):
        raise FileNotFoundError("Style rule not found")
    data["rules"] = [rule for rule in data["rules"] if rule.get("id") != rule_id]
    # Dismissal IDs are source hashes tied to rules; discard rule-specific entries.
    data["dismissals"] = {
        k: v for k, v in data["dismissals"].items() if v.get("rule_id") != rule_id
    }
    _write(slug, data)
    return {"deleted": rule_id}


def _scan(slug: str, state: dict) -> dict:
    chapters = _chapters(slug)
    if len(chapters) > MAX_CHAPTERS or sum(len(c["text"].encode("utf-8")) for c in chapters) > MAX_BYTES:
        raise ValueError("Style audit supports up to 120 chapters and 12 MB of prose")
    found = []
    truncated = False
    for chapter in chapters:
        text = chapter["text"]
        fingerprint = _hash(text)
        for rule in state["rules"]:
            phrase = rule["phrase"]
            pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
                                 0 if rule.get("case_sensitive") else re.IGNORECASE)
            for match in pattern.finditer(text):
                if len(found) >= MAX_FINDINGS:
                    truncated = True
                    break
                begin, end = match.span()
                key = _hash("|".join([rule["id"], chapter["path"], fingerprint, str(begin), match.group()]))[:24]
                found.append({
                    "id": key, "rule_id": rule["id"], "category": rule["category"],
                    "phrase": phrase, "preferred": rule.get("preferred", ""),
                    "note": rule.get("note", ""), "path": chapter["path"],
                    "title": chapter["title"], "source_hash": fingerprint,
                    "line": text.count("\n", 0, begin) + 1,
                    "excerpt": text[max(0, begin - 65):min(len(text), end + 75)].replace("\n", " ").strip(),
                    "matched": match.group(),
                    "dismissed": key in state["dismissals"],
                    "dismissal_reason": state["dismissals"].get(key, {}).get("reason", ""),
                })
            if truncated:
                break
        if truncated:
            break
    return {"findings": found, "truncated": truncated, "chapters": len(chapters)}


def audit(slug: str) -> dict:
    state = _load(slug)
    report = _scan(slug, state)
    items = report["findings"]
    return {
        "rules": state["rules"], **report,
        "outstanding": sum(not row["dismissed"] for row in items),
        "dismissed": sum(row["dismissed"] for row in items),
        "limits": "Exact phrase/word-boundary matching only. Intended usages, dialogue and false positives require author review. Nothing is rewritten.",
    }


def decide(slug: str, finding_id: str, action: str, reason: str = "") -> dict:
    if action not in ("dismiss", "reopen"):
        raise ValueError("Unknown style-audit decision")
    if action == "dismiss" and not 8 <= len(reason.strip()) <= 500:
        raise ValueError("Explain the dismissal in 8–500 characters")
    state = _load(slug)
    # Recompute against the current manuscript: old chapter versions cannot
    # receive new decisions and source edits automatically invalidate waivers.
    current = _scan(slug, state)
    item = next((row for row in current["findings"] if row["id"] == finding_id), None)
    if not item:
        raise FileNotFoundError("Style finding not present in the current manuscript")
    if action == "dismiss":
        if len(state["dismissals"]) >= MAX_FINDINGS and finding_id not in state["dismissals"]:
            raise ValueError("Style dismissal history is full")
        state["dismissals"][finding_id] = {
            "rule_id": item["rule_id"], "reason": reason.strip(), "created_at": _now(),
        }
    else:
        if finding_id not in state["dismissals"]:
            raise ValueError("Style finding is not dismissed")
        state["dismissals"].pop(finding_id)
    _write(slug, state)
    return audit(slug)
