"""Author-approved, local-only sequential book drafting with persisted candidates.

A book can be drafted in order across browser requests. Every chapter result is a
candidate until the author approves it; canonical manuscript files are never
overwritten automatically. The queue is persisted per project and resumable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .binder import sync_binder
from .generation import generate, generate_complete_prose
from .models import ProviderConfig
from .storage import get_project, project_root, read_text, save_text

MAX_CHAPTERS = 80
MAX_BRIEF = 3000
MAX_CONTEXT = 16000
_RUNNING: set[str] = set()
_LOCKS: dict[str, asyncio.Lock] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_file(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "book-studio.json"


def _output(slug: str, chapter: int) -> Path:
    return project_root(slug) / ".ember" / "book-candidates" / f"chapter-{chapter:03d}.md"


def _write(slug: str, state: dict) -> dict:
    path = _state_file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    state["updated_at"] = _now()
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return state


def load_state(slug: str) -> dict:
    path = _state_file(slug)
    if not path.is_file():
        return {"configured": False, "chapters": [], "running": slug in _RUNNING}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("chapters"), list):
        raise ValueError("Book Studio state is invalid")
    # A crashed process cannot leave a chapter permanently stuck in 'generating'.
    # Preserve its attempt count, but make it explicitly retryable.
    if slug not in _RUNNING and any(ch.get("status") == "generating" for ch in state["chapters"]):
        for chapter in state["chapters"]:
            if chapter.get("status") == "generating":
                chapter["status"] = "failed"
                chapter["error"] = "Generation interrupted; you can retry this chapter"
        _write(slug, state)
    state["running"] = slug in _RUNNING
    return state


def configure(slug: str, *, premise: str, voice: str, chapters: list[dict],
              target_words: int = 1500) -> dict:
    if not premise.strip() or len(premise) > 8000:
        raise ValueError("A premise of up to 8000 characters is required")
    if len(voice) > 3000:
        raise ValueError("Voice instructions are too long")
    if not 1 <= len(chapters) <= MAX_CHAPTERS or not 300 <= target_words <= 5000:
        raise ValueError("Plan requires 1-80 chapters with 300-5000 target words each")
    if slug in _RUNNING:
        raise ValueError("Cannot edit plan during an active generation")
    current = load_state(slug)
    if current["configured"] and any(ch["status"] not in ("planned", "failed") for ch in current["chapters"]):
        raise ValueError("Existing candidate chapters must be resolved before replacing the plan")
    cleaned = []
    for index, chapter in enumerate(chapters, 1):
        title = str(chapter.get("title", "")).strip()
        brief = str(chapter.get("brief", "")).strip()
        if not title or len(title) > 200 or not brief or len(brief) > MAX_BRIEF:
            raise ValueError(f"Chapter {index} requires a title and a brief")
        cleaned.append({"number": index, "title": title, "brief": brief,
                        "status": "planned", "candidate_words": 0, "attempts": 0,
                        "approved_at": None, "error": ""})
    return _write(slug, {"configured": True, "premise": premise.strip(), "voice": voice.strip(),
                         "target_words": target_words, "chapters": cleaned})


def revise_chapter_brief(slug: str, number: int, title: str, brief: str) -> dict:
    state = load_state(slug)
    if slug in _RUNNING:
        raise ValueError("Cannot edit a chapter during generation")
    if not state["configured"] or not 1 <= number <= len(state["chapters"]):
        raise FileNotFoundError("Chapter not in this plan")
    ch = state["chapters"][number - 1]
    if ch["status"] not in ("planned", "failed"):
        raise ValueError("Only planned or failed chapter briefs can be changed")
    if not title.strip() or len(title) > 200 or not brief.strip() or len(brief) > MAX_BRIEF:
        raise ValueError("Chapter title and brief must be provided")
    ch["title"] = title.strip()
    ch["brief"] = brief.strip()
    ch["status"] = "planned"
    ch["attempts"] = 0
    ch["error"] = ""
    _write(slug, state)
    return ch


def _local_model(config: ProviderConfig) -> None:
    address = urlparse(config.base_url)
    if config.provider != "ollama" or address.scheme != "http" or address.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Book Studio only accepts local Ollama on loopback; external models are not allowed")
    if not config.model.strip():
        raise ValueError("Select an installed local writing model")
    # Ollama's *-cloud model aliases send prompts to a hosted provider even
    # when the API itself is on 127.0.0.1. Never use them for private books.
    if re.search(r"(?:-cloud|:cloud)(?:$|[-:])", config.model.casefold()):
        raise ValueError("Ollama cloud models are not permitted for private Book Studio drafting")


async def suggest_outline(slug: str, *, premise: str, voice: str, chapter_count: int,
                          config: ProviderConfig) -> list[dict]:
    _local_model(config)
    if not premise.strip() or len(premise) > 8000 or len(voice) > 3000:
        raise ValueError("Provide a premise (up to 8000 characters) and optional voice guidance")
    if not 1 <= chapter_count <= MAX_CHAPTERS:
        raise ValueError("Chapter count must be between 1 and 80")
    project = get_project(slug)
    context = []
    for path in sorted(p for p in project["files"] if p.startswith(("world/", "characters/", "style/", "timeline/", "relationships/")) and p.endswith(".md") and not p.endswith("README.md"))[:20]:
        context.append(f"### {path}\n{read_text(slug, path)[:1600]}")
    prompt = (
        f"PREMISE: {premise}\nVOICE: {voice}\nEXISTING CANON:\n"
        + "\n\n".join(context)[:10000]
        + f"\n\nPropose exactly {chapter_count} distinct chapters spanning a complete book: "
        "setup, escalation, character choices, midpoint, consequences and earned resolution. "
        "Respect the author's existing canon; label new developments as proposals. "
        'Return JSON only: {"chapters": [{"title":"...", "brief":"concrete scene beats, POV, character movement and plot consequence"}]}. '
        "Make every brief specific and non-repetitive."
    )
    response = await generate(config, [
        {"role": "system", "content": "You are an author-led novel outlining collaborator. Return only valid JSON, not prose."},
        {"role": "user", "content": prompt},
    ], json_mode=True, temperature=0.7, max_output_tokens=min(8192, 500 + 175 * chapter_count))
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.I)
    parsed = json.loads(stripped)
    chapters = parsed.get("chapters") if isinstance(parsed, dict) else None
    if not isinstance(chapters, list) or len(chapters) != chapter_count:
        raise ValueError("Outline model returned an invalid chapter count; retry or create chapters manually")
    cleaned = []
    for entry in chapters:
        if not isinstance(entry, dict):
            raise ValueError("Outline model returned a malformed chapter")
        title, brief = str(entry.get("title", "")).strip(), str(entry.get("brief", "")).strip()
        if not title or not brief or len(title) > 200 or len(brief) > MAX_BRIEF:
            raise ValueError("Outline model produced an invalid chapter proposal")
        cleaned.append({"title": title, "brief": brief})
    return cleaned


def _prior_chapter_text(slug: str, entry: dict) -> str:
    """Read actual approved prose or a pending local candidate, never an AI summary."""
    number = int(entry["number"])
    if entry["status"] == "approved":
        return read_text(slug, f"manuscript/book-studio/chapter-{number:03d}.md")
    if entry["status"] == "candidate":
        source = _output(slug, number)
        return source.read_text(encoding="utf-8") if source.is_file() else ""
    return ""


def _continuity_digest(slug: str, state: dict, chapter_index: int) -> str:
    """Small, reproducible excerpts from earlier chapters, not inferred story facts."""
    if chapter_index < 2:
        return ""
    earlier = [entry for entry in state["chapters"][:chapter_index-1]
               if entry["status"] in ("approved", "candidate")]
    # Anchor the opening and prefer recent developments. Limit the number of
    # chapters and total text to preserve budget for actual scene continuity.
    chosen = {entry["number"] for entry in earlier[-9:]}
    if earlier:
        chosen.add(earlier[0]["number"])
    parts = []
    for entry in earlier:
        if entry["number"] not in chosen:
            continue
        prose = _prior_chapter_text(slug, entry).strip()
        if not prose:
            continue
        # Original openings/endings are evidence excerpts, not authoritative
        # summaries; they may omit important interior developments.
        excerpt = prose[:130].replace("\n", " ").strip()
        ending = prose[-270:].replace("\n", " ").strip()
        parts.append(
            f"Ch. {entry['number']} {entry['title']} [{entry['status']}]: "
            f"opening: {excerpt}; ending: {ending}"
        )
    return "### Historical chapter excerpts (incomplete, source-grounded)\n" + "\n".join(parts)[:4200] if parts else ""


def _context(slug: str, state: dict, chapter_index: int) -> str:
    """Reserve context space for the immediate prior chapter and core canon."""
    from .manuscript_intelligence import list_promises

    parts = []
    remaining = MAX_CONTEXT

    def append(section: str, maximum: int):
        nonlocal remaining
        if not section or remaining < 80:
            return
        clipped = section[:min(maximum, remaining)]
        parts.append(clipped)
        remaining -= len(clipped) + 2

    if chapter_index > 0:
        prior = _prior_chapter_text(slug, state["chapters"][chapter_index - 1])
        if prior:
            append("### Previous chapter ending (original prose)\n" + prior[-5200:], 5400)

    # Author-supplied canonical facts outrank historical prose excerpts.
    # A fixed reserve prevents a large dossier from crowding out the current
    # chapter's immediate continuity and authored story promises.
    project = get_project(slug)
    priorities = ("characters/", "world/", "relationships/", "style/", "timeline/", "planning/")
    paths = [p for p in project["files"]
             if p.startswith(priorities)
             and p.endswith((".md", ".txt")) and not p.endswith("README.md")]
    paths.sort(key=lambda path: (next((i for i, prefix in enumerate(priorities)
                                     if path.startswith(prefix)), len(priorities)), path))
    canon_budget = min(6900, remaining)
    for path in paths[:30]:
        if canon_budget < 80 or remaining < 80:
            break
        value = read_text(slug, path).strip()
        if value:
            section = f"### Author canon: {path}\n{value}"
            before = remaining
            append(section, min(3000, canon_budget))
            canon_budget -= before - remaining

    promises = [record for record in list_promises(slug) if record.get("status") == "open"][:12]
    if promises:
        body = "\n".join(
            f"- {p['title']}: tracking phrase '{p['tracking_phrase']}'; "
            f"author's intention: {p.get('intention', '')[:120]}"
            for p in promises
        )
        append("### Open author-tracked story promises (NOT automatically fulfilled)\n" + body, 1700)

    append(_continuity_digest(slug, state, chapter_index), 3500)
    return "\n\n".join(parts)[:MAX_CONTEXT]


async def draft_next(slug: str, config: ProviderConfig) -> dict:
    _local_model(config)
    lock = _LOCKS.setdefault(slug, asyncio.Lock())
    if lock.locked():
        raise ValueError("A chapter is already generating for this project")
    async with lock:
        state = load_state(slug)
        if not state["configured"]:
            raise ValueError("Configure a book plan first")
        # Continue through planned chapters, even when earlier drafts await review.
        # Candidate text supplies context, but canonical files are never overwritten.
        index = next((i for i, ch in enumerate(state["chapters"]) if ch["status"] == "planned" or (ch["status"] == "failed" and ch.get("attempts", 0) < 3)), None)
        if index is None:
            raise ValueError("No chapters awaiting drafting")
        chapter = state["chapters"][index]
        if chapter["attempts"] >= 3:
            raise ValueError("Chapter reached the three-attempt limit")
        chapter["status"] = "generating"
        chapter["attempts"] += 1
        _write(slug, state)
        _RUNNING.add(slug)
        try:
            context = _context(slug, state, index)
            system = (
                "You are a skilled long-form novelist working on one chapter of a coherent book. "
                "Write publishable narrative prose only, with specific character voice, action, distinct dialogue, "
                "scene causality, tension changes and earned emotional development. "
                "Preserve all canon supplied in context. Do not summarize, outline, explain, pad, repeat, or "
                "invent contradictions. The author will independently review this candidate. "
                "Do not repeat earlier chapter material. Close this chapter with an earned turn."
            )
            plan = "\n".join(
                f"Chapter {item['number']}: {item['title']} — {item['brief'][:420]}"
                for item in state["chapters"]
            )[:14000]
            prompt = (
                f"BOOK PREMISE:\n{state['premise']}\n\n"
                f"VOICE / STYLE:\n{state['voice']}\n\n"
                f"WHOLE-BOOK CHAPTER ROADMAP:\n{plan}\n\n"
                f"YOU ARE WRITING CHAPTER {index+1} OF {len(state['chapters'])}: {chapter['title']}\n"
                f"REQUIRED BEATS:\n{chapter['brief']}\n\n"
                f"CANON & PREVIOUS CHAPTER:\n{context}\n\n"
                f"Target at least {state['target_words']} words. "
                "Write full chapter prose rather than a synopsis. Deliver an ending that prepares the next chapter."
            )
            prose = await generate_complete_prose(
                config, [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                min_words=state["target_words"], max_passes=5
            )
            words = len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", prose))
            if words < state["target_words"] * .6:
                raise ValueError(f"Generated only {words} words; chapter is too short for the requested target")
            result = f"# {chapter['title']}\n\n{prose.strip()}\n"
            file = _output(slug, index + 1)
            file.parent.mkdir(parents=True, exist_ok=True)
            tmp = file.with_suffix(".md.tmp")
            tmp.write_text(result, encoding="utf-8")
            tmp.replace(file)
            chapter["status"] = "candidate"
            chapter["candidate_words"] = words
            chapter["candidate_hash"] = hashlib.sha256(result.encode("utf-8")).hexdigest()
            chapter["error"] = ""
            return {"chapter": chapter, "preview": result}
        except Exception as exc:
            chapter["status"] = "failed"
            chapter["error"] = str(exc)[:500]
            raise
        finally:
            _RUNNING.discard(slug)
            _write(slug, state)


def candidate(slug: str, number: int) -> dict:
    state = load_state(slug)
    if not state["configured"] or number < 1 or number > len(state["chapters"]):
        raise FileNotFoundError("Chapter not in this plan")
    chapter = state["chapters"][number - 1]
    path = _output(slug, number)
    if not path.is_file() or chapter["status"] not in ("candidate", "approved"):
        raise FileNotFoundError("Draft candidate is unavailable")
    return {"chapter": chapter, "content": path.read_text(encoding="utf-8")}


def edit_candidate(slug: str, number: int, content: str) -> dict:
    state = load_state(slug)
    if slug in _RUNNING:
        raise ValueError("Cannot edit candidate during generation")
    chapter_info = candidate(slug, number)
    chapter = state["chapters"][number - 1]
    if chapter["status"] != "candidate":
        raise ValueError("Only pending candidates can be edited")
    if not content.strip() or len(content) > 1_000_000:
        raise ValueError("Candidate content must be between 1 and 1,000,000 characters")
    file = _output(slug, number)
    # Preserve earlier versions for author-driven editing and recovery.
    revisions = project_root(slug) / ".ember" / "book-candidate-revisions" / f"chapter-{number:03d}"
    revisions.mkdir(parents=True, exist_ok=True)
    backup = revisions / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.md"
    backup.write_text(chapter_info["content"], encoding="utf-8")
    tmp = file.with_suffix(".md.tmp")
    normalized = content.rstrip() + "\n"
    tmp.write_text(normalized, encoding="utf-8")
    tmp.replace(file)
    chapter["candidate_words"] = len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", normalized))
    chapter["candidate_hash"] = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    chapter["edited_by_author"] = True
    _write(slug, state)
    return {"chapter": chapter, "content": normalized}


def approve(slug: str, number: int) -> dict:
    state = load_state(slug)
    if slug in _RUNNING:
        raise ValueError("Cannot approve while a chapter is generating")
    chapter_info = candidate(slug, number)
    chapter = state["chapters"][number - 1]
    if chapter["status"] != "candidate":
        raise ValueError("Only pending chapter candidates can be approved")
    text = chapter_info["content"]
    actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if actual_hash != chapter.get("candidate_hash"):
        raise ValueError("Candidate changed on disk; review and regenerate before approval")
    output = f"manuscript/book-studio/chapter-{number:03d}.md"
    # Never replace a user's existing chapter: approving an AI draft is an opt-in
    # new-file action. Existing manuscripts require a separate diff workflow.
    if (project_root(slug) / output).exists():
        raise ValueError("A manuscript already exists at this path; manual merge required")
    result = save_text(slug, output, text)
    chapter["status"] = "approved"
    chapter["approved_at"] = _now()
    _write(slug, state)
    sync_binder(slug)
    return {"chapter": chapter, "saved": result}


def decline(slug: str, number: int) -> dict:
    state = load_state(slug)
    if not state["configured"] or number < 1 or number > len(state["chapters"]):
        raise FileNotFoundError("Chapter not in this plan")
    if slug in _RUNNING:
        raise ValueError("Cannot decline while a chapter is generating")
    chapter = state["chapters"][number - 1]
    if chapter["status"] != "candidate":
        raise ValueError("Only pending candidates can be declined")
    chapter["status"] = "failed"
    chapter["error"] = "Author declined this draft; request another candidate"
    _write(slug, state)
    return chapter
