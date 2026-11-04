"""Author-approved, evidence-led chapter revision proposals.

Revisions are held apart from book candidates. They use only accepted current
reader findings, a local Ollama model, and a strict author acceptance step.
The original candidate is versioned by Book Studio before any replacement.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from .book_studio import _local_model, candidate, edit_candidate, load_state
from .book_reviews import brief
from .generation import generate
from .models import ProviderConfig
from .quality_clinic import check_text
from .storage import project_root

MAX_CHARS = 110_000
MAX_PROPOSALS = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _folder(slug: str, number: int) -> Path:
    return project_root(slug) / ".ember" / "book-revisions" / f"chapter-{number:03d}"


def _index(slug: str, number: int) -> Path:
    return _folder(slug, number) / "index.json"


def _load(slug: str, number: int) -> dict:
    # Enforce current project/chapter validity before accessing revision history.
    candidate(slug, number)
    path = _index(slug, number)
    if not path.is_file():
        return {"number": number, "proposals": []}
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not isinstance(result.get("proposals"), list):
        raise ValueError("Revision history is corrupt")
    return result


def _save(slug: str, number: int, history: dict) -> None:
    target = _index(slug, number)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_suffix(".json.tmp")
    stage.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    stage.replace(target)


def _proposal_path(slug: str, number: int, proposal_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", proposal_id):
        raise ValueError("Invalid revision proposal identifier")
    return _folder(slug, number) / f"{proposal_id}.md"


def _diff_metrics(original: str, proposed: str) -> dict:
    before = original.splitlines()
    after = proposed.splitlines()
    diffs = SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    return {
        "original_words": len(original.split()),
        "proposed_words": len(proposed.split()),
        "added_lines": sum(j2 - j1 for name, _, _, j1, j2 in diffs if name in ("insert", "replace")),
        "removed_lines": sum(i2 - i1 for name, i1, i2, _, _ in diffs if name in ("delete", "replace")),
        "unchanged_lines": sum(i2 - i1 for name, i1, i2, _, _ in diffs if name == "equal"),
    }


def list_proposals(slug: str, number: int) -> dict:
    data = _load(slug, number)
    current = _hash(candidate(slug, number)["content"])
    for item in data["proposals"]:
        item["stale"] = item["source_hash"] != current
    return data


def get_proposal(slug: str, number: int, proposal_id: str) -> dict:
    history = list_proposals(slug, number)
    proposal = next((p for p in history["proposals"] if p["id"] == proposal_id), None)
    if proposal is None:
        raise FileNotFoundError("Revision proposal not found")
    path = _proposal_path(slug, number, proposal_id)
    if not path.is_file():
        raise FileNotFoundError("Revision candidate is missing")
    proposed = path.read_text(encoding="utf-8")
    original = candidate(slug, number)["content"]
    return {**proposal, "proposed_text": proposed, "current_text": original,
            "metrics": _diff_metrics(original, proposed)}


async def propose(slug: str, number: int, config: ProviderConfig, author_direction: str = "") -> dict:
    _local_model(config)
    if len(author_direction) > 2000:
        raise ValueError("Author direction exceeds 2000 characters")
    state = load_state(slug)
    chapter = state["chapters"][number - 1] if 1 <= number <= len(state["chapters"]) else None
    if chapter is None or chapter["status"] != "candidate":
        raise ValueError("Only unapproved book candidates can be revised")
    source = candidate(slug, number)["content"]
    if len(source) > MAX_CHARS or len(source.split()) < 25:
        raise ValueError("Chapter must contain 25 words and no more than 110,000 characters")
    accepted = brief(slug, number)["accepted"]
    if not accepted and not author_direction.strip():
        raise ValueError("Accept a reader recommendation or provide your own revision direction")
    instructions = [
        f"CHAPTER {number}: {chapter['title']}",
        f"CHAPTER BRIEF: {chapter['brief']}",
        f"AUTHOR'S VOICE: {state.get('voice', '')}",
        f"BOOK PREMISE: {state.get('premise', '')}",
        "REVISION GOALS (only these are authorized):",
    ]
    for i, item in enumerate(accepted[:20], 1):
        instructions.append(f"{i}. [{item['category']}] {item['suggestion']} | Evidence: {item['quote']} | Author note: {item.get('author_note', '')}")
    if author_direction.strip():
        instructions.append("AUTHOR'S DIRECT INSTRUCTIONS: " + author_direction.strip())
    instructions.extend([
        "Return the COMPLETE revised chapter in plain Markdown, no prefatory notes.",
        "Maintain existing plot facts, character identity, consent, continuity, point of view and tone unless directly instructed otherwise.",
        "Do not compress the chapter into a summary; preserve scenes and their dramatic trajectory.",
        "ORIGINAL CHAPTER:\n" + source,
    ])
    answer = await generate(config, [
        {"role": "system", "content": "You are a disciplined fiction line/development editor. The author has final authority. Return complete revised chapter prose, preserving story canon and distinctive voice."},
        {"role": "user", "content": "\n\n".join(instructions)},
    ], temperature=0.55, max_output_tokens=14000)
    proposed = answer.strip()
    proposed = re.sub(r"^\x60{3}(?:markdown|md)?\s*|\s*\x60{3}$", "", proposed, flags=re.I).strip() + "\n"
    if len(proposed) > MAX_CHARS or len(proposed.split()) < max(25, int(len(source.split()) * .6)):
        raise ValueError("Model returned an incomplete or excessively short revision; nothing was saved")
    if _hash(proposed) == _hash(source):
        raise ValueError("Model returned unchanged prose; nothing to review")
    # Check again after the model request: author may have edited the candidate meanwhile.
    if _hash(candidate(slug, number)["content"]) != _hash(source):
        raise ValueError("Candidate changed during generation; revision discarded to preserve author edits")
    history = _load(slug, number)
    identifier = uuid4().hex
    path = _proposal_path(slug, number, identifier)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(proposed, encoding="utf-8")
    tmp.replace(path)
    report_before = check_text(source)["metrics"]
    report_after = check_text(proposed)["metrics"]
    item = {
        "id": identifier, "source_hash": _hash(source), "proposed_hash": _hash(proposed),
        "created_at": _now(), "model": config.model, "status": "proposed",
        "author_direction": author_direction.strip(), "accepted_findings": len(accepted),
        "source_words": len(source.split()), "proposed_words": len(proposed.split()),
        "quality_before": report_before, "quality_after": report_after,
    }
    history["proposals"] = [item, *history["proposals"]][:MAX_PROPOSALS]
    _save(slug, number, history)
    return get_proposal(slug, number, identifier)


def decide(slug: str, number: int, proposal_id: str, action: str) -> dict:
    if action not in ("accept", "reject"):
        raise ValueError("Unknown revision decision")
    data = list_proposals(slug, number)
    item = next((p for p in data["proposals"] if p["id"] == proposal_id), None)
    if item is None:
        raise FileNotFoundError("Revision not found")
    if item["status"] != "proposed":
        raise ValueError("This revision has already been decided")
    if item["stale"]:
        raise ValueError("Chapter changed after the revision was proposed; request a new revision")
    if action == "accept":
        proposed = _proposal_path(slug, number, proposal_id).read_text(encoding="utf-8")
        if _hash(proposed) != item["proposed_hash"]:
            raise ValueError("Revision content changed on disk and cannot be accepted")
        # edit_candidate archives the original candidate before updating it.
        edit_candidate(slug, number, proposed)
        item["status"] = "accepted"
    else:
        item["status"] = "rejected"
    item["decided_at"] = _now()
    _save(slug, number, data)
    return item
