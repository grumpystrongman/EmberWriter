"""Author-led independent chapter reader panels; only local Ollama allowed.

Findings are linked to exact quotes verified in the candidate. Reviews never
modify drafts or manuscripts and grow stale when the author changes the draft.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .book_studio import _local_model, candidate
from .generation import generate
from .models import ProviderConfig
from .storage import project_root

PERSONAS = {
    "genre_fan": ("Genre Fan", "Assess immersion, emotional payoff, genre expectations, character attachment, and reading momentum."),
    "developmental_editor": ("Developmental Editor", "Assess structure, causality, agency, stakes, pacing, character arcs, and setup/payoff."),
    "line_editor": ("Line Editor", "Assess voice, dialogue distinction, clarity, sentence rhythm, repeated imagery, and formulaic prose."),
}
CATEGORIES = {"structure", "pacing", "character", "voice", "dialogue", "clarity", "continuity", "style", "payoff"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _file(slug: str, number: int) -> Path:
    return project_root(slug) / ".ember" / "book-reviews" / f"chapter-{number:03d}.json"


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load(slug: str, number: int) -> dict:
    path = _file(slug, number)
    if not path.exists():
        return {"number": number, "reviews": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
        raise ValueError("Invalid reader review history")
    return data


def _write(slug: str, number: int, data: dict):
    path = _file(slug, number)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def history(slug: str, number: int) -> dict:
    content = candidate(slug, number)["content"]
    data = _load(slug, number)
    for item in data["reviews"]:
        item["stale"] = item.get("content_hash") != _hash(content)
    return data


def _parse(raw: str) -> dict:
    text = raw.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = re.sub(r"^" + fence + r"(?:json)?\s*|\s*" + fence + r"$", "", text, flags=re.I)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Reader did not return valid structured JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("Reader returned invalid evaluation")
    return obj


def _findings(raw: list, content: str) -> tuple[list, int]:
    if not isinstance(raw, list) or len(raw) > 10:
        raise ValueError("Reader findings must be a list of up to ten")
    verified = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        category = str(item.get("category", "")).strip()
        issue = str(item.get("issue", "")).strip()
        suggestion = str(item.get("suggestion", "")).strip()
        if (category not in CATEGORIES or not quote or quote not in content
                or not issue or not suggestion or len(quote) > 300
                or len(issue) > 500 or len(suggestion) > 650):
            continue
        verified.append({
            "id": f"f{index+1}", "category": category, "quote": quote,
            "issue": issue, "suggestion": suggestion,
            "decision": "pending", "author_note": "",
        })
    return verified, len(raw) - len(verified)


async def evaluate(slug: str, number: int, persona: str, config: ProviderConfig, focus: str = "") -> dict:
    _local_model(config)
    if persona not in PERSONAS:
        raise ValueError("Unknown review persona")
    if len(focus) > 1000:
        raise ValueError("Review focus exceeds 1000 characters")
    content = candidate(slug, number)["content"]
    if not 25 <= len(content.split()) or len(content) > 110_000:
        raise ValueError("Chapter must have 25 or more words and at most 110,000 characters")
    name, lens = PERSONAS[persona]
    system = (
        f"You are an independent {name}, not the author. {lens} "
        "Respect the author's unusual style and don't rewrite anything. "
        "Only identify problems proven by exact quotes from the candidate; "
        "never invent quotations, events or flaws. Return structured JSON only."
    )
    prompt = (
        f"CHAPTER {number}; FOCUS: {focus or 'general critique'}\n"
        'Return JSON: {"verdict":"brief reader verdict", "strengths":["specific strengths"], '
        '"scores":{"engagement":1,"clarity":1,"pacing":1,"character":1,"voice":1}, '
        '"findings":[{"category":"pacing","quote":"exact passage","issue":"why","suggestion":"revision option"}]}. '
        "Scores 1-5. Up to 6 genuinely useful findings, or empty list. "
        "Quote directly and exactly from the chapter.\n\nCHAPTER CANDIDATE:\n" + content
    )
    raw = await generate(config, [
        {"role": "system", "content": system}, {"role": "user", "content": prompt},
    ], json_mode=True, temperature=0.35, max_output_tokens=3000)
    parsed = _parse(raw)
    verdict = str(parsed.get("verdict", "")).strip()
    strengths = parsed.get("strengths", [])
    scores = parsed.get("scores", {})
    if not verdict or len(verdict) > 1200 or not isinstance(strengths, list) or not isinstance(scores, dict):
        raise ValueError("Reader verdict is incomplete")
    dimensions = ("engagement", "clarity", "pacing", "character", "voice")
    if any(type(scores.get(key)) is not int or scores[key] not in range(1, 6) for key in dimensions):
        raise ValueError("Reader returned invalid dimension scores")
    findings, rejected = _findings(parsed.get("findings", []), content)
    record = {
        "id": hashlib.sha256((_now() + persona + content).encode()).hexdigest()[:20],
        "persona": persona, "persona_name": name, "model": config.model,
        "content_hash": _hash(content), "created_at": _now(), "verdict": verdict,
        "strengths": [s[:250] for s in strengths[:4] if isinstance(s, str) and s.strip()],
        "scores": {key: scores[key] for key in dimensions},
        "findings": findings, "stale": False, "focus": focus.strip(),
        "unverified_findings_rejected": rejected,
    }
    data = _load(slug, number)
    data["reviews"] = [record, *data["reviews"]][:80]
    _write(slug, number, data)
    return record


def decide(slug: str, number: int, review_id: str, finding_id: str, action: str,
           author_note: str = "") -> dict:
    if action not in ("accept", "dismiss", "reopen") or len(author_note) > 1400:
        raise ValueError("Invalid review decision")
    data = history(slug, number)
    item = next((r for r in data["reviews"] if r["id"] == review_id), None)
    if item is None:
        raise FileNotFoundError("Review not found")
    if item["stale"]:
        raise ValueError("This evaluation is from an older draft; run a fresh review")
    finding = next((f for f in item["findings"] if f["id"] == finding_id), None)
    if finding is None:
        raise FileNotFoundError("Finding not found")
    finding["decision"] = {"accept": "accepted", "dismiss": "dismissed", "reopen": "pending"}[action]
    finding["author_note"] = author_note.strip()
    _write(slug, number, data)
    return finding


def brief(slug: str, number: int) -> dict:
    data = history(slug, number)
    accepted = [
        {
            "persona": review["persona_name"], "category": finding["category"],
            "quote": finding["quote"], "issue": finding["issue"],
            "suggestion": finding["suggestion"], "author_note": finding.get("author_note", ""),
        }
        for review in data["reviews"] if not review["stale"]
        for finding in review["findings"] if finding.get("decision") == "accepted"
    ]
    return {
        "chapter": number, "accepted": accepted, "count": len(accepted),
        "guidance": "Author-approved revision brief. No draft or manuscript was changed.",
    }
