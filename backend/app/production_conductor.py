"""Durable author-led book production conductor.

Supervises the existing book-jobs generation queue, performs optional local
independent reader critiques sequentially, stops at an author approval gate,
then runs local editorial/preflight once every planned chapter is approved.
No manuscript candidate is accepted, revised or published automatically.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import book_jobs, book_reviews, book_studio, editorial_board, production_preflight
from .book_studio import _local_model
from .models import ProviderConfig
from .storage import get_project, list_projects, project_root

PERSONAS = ("developmental_editor", "line_editor", "genre_fan")
_ACTIVE: dict[str, asyncio.Task] = {}
POLL_SECONDS = 1.5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "production-conductor.json"


def _load(slug: str) -> dict | None:
    path = _path(slug)
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not state.get("id") or not isinstance(state.get("provider"), dict):
        raise ValueError("Production conductor checkpoint is invalid")
    return state


def _write(slug: str, state: dict):
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _now()
    # Keep a short, author-visible event journal. No prose or prompts belong in
    # the orchestration record; source text stays in the project's own files.
    previous = None
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = None
    events = state.get("events", [])
    if not isinstance(events, list):
        events = []
    changed = (previous is None or
               previous.get("status") != state.get("status") or
               previous.get("phase") != state.get("phase") or
               previous.get("message") != state.get("message"))
    if changed:
        events = [{
            "at": now, "status": state.get("status", ""),
            "phase": state.get("phase", ""), "message": str(state.get("message", ""))[:350],
        }, *events][:120]
    state["events"] = events
    state["updated_at"] = now
    stage = path.with_suffix(".json.tmp")
    stage.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    stage.replace(path)


def _running(slug: str) -> bool:
    job = _ACTIVE.get(slug)
    return bool(job and not job.done())


def _model(state: dict) -> ProviderConfig:
    config = ProviderConfig.model_validate(state["provider"])
    _local_model(config)
    return config


def _chapters(slug: str) -> list[dict]:
    state = book_studio.load_state(slug)
    if not state.get("configured"):
        raise ValueError("Create a Book Studio plan before using the production conductor")
    return state["chapters"]


def _fingerprint(slug: str, number: int) -> str:
    content = book_studio.candidate(slug, number)["content"]
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _next_review(slug: str, state: dict) -> tuple[int, str] | None:
    for chapter in _chapters(slug):
        if chapter["status"] not in ("candidate", "approved"):
            continue
        # Approved candidates have already passed the author gate. Reader
        # critiques are only proposed for unapproved draft candidates.
        if chapter["status"] == "approved":
            continue
        number = chapter["number"]
        version = _fingerprint(slug, number)
        for persona in state["personas"]:
            key = f"{number}:{persona}"
            if state["reviews_done"].get(key) != version:
                return number, persona
    return None


def status(slug: str) -> dict:
    record = _load(slug)
    if record is None:
        return {"exists": False, "status": "idle", "active": False}
    chapters = _chapters(slug)
    result = {k: v for k, v in record.items() if k != "provider"}
    handoff_current = None
    if record["status"] == "completed":
        freshness = editorial_board.freshness(slug)
        handoff_current = (
            freshness["current"] and
            freshness.get("scan_id") == record.get("editorial_scan_id") and
            all(ch["status"] == "approved" for ch in chapters)
        )
    result.update({
        "exists": True, "active": _running(slug),
        "handoff_current": handoff_current,
        "model": record["provider"].get("model", ""),
        "total": len(chapters),
        "drafted": sum(ch["status"] in ("candidate", "approved") for ch in chapters),
        "approved": sum(ch["status"] == "approved" for ch in chapters),
        "candidates": sum(ch["status"] == "candidate" for ch in chapters),
        "chapters": [{
            "number": ch["number"], "title": ch["title"], "status": ch["status"],
            "candidate_words": ch.get("candidate_words", 0),
            "reviews": [
                {"persona": persona, "current": (
                    ch["status"] == "candidate" and record["reviews_done"].get(f"{ch['number']}:{persona}")
                    == ch.get("candidate_hash")
                )}
                for persona in record["personas"]
            ],
        } for ch in chapters],
    })
    return result


def _spawn(slug: str, record: dict) -> None:
    if _running(slug):
        raise ValueError("Production conductor is already active")
    _ACTIVE[slug] = asyncio.create_task(_worker(slug, record["id"]), name=f"production-conductor-{slug}")


def start(slug: str, config: ProviderConfig, personas: list[str]) -> dict:
    _local_model(config)
    chapters = _chapters(slug)
    if not chapters:
        raise ValueError("No planned chapters")
    if len(personas) != len(set(personas)) or any(p not in PERSONAS for p in personas) or len(personas) > 3:
        raise ValueError("Select up to three distinct local reader personas")
    if _running(slug) or book_jobs._running(slug):
        raise ValueError("A book production or drafting task is already active")
    previous = _load(slug)
    if previous and previous["status"] not in ("completed", "needs_attention", "paused", "awaiting_author"):
        raise ValueError("An unfinished production conductor already exists; resume or inspect it")
    existing_draft = book_jobs.status(slug)
    if existing_draft.get("status") in ("queued", "running"):
        raise ValueError("Book Studio drafting queue already active")
    record = {
        "id": uuid4().hex, "created_at": _now(), "updated_at": _now(),
        "status": "queued", "phase": "draft",
        "provider": {"provider": "ollama", "base_url": config.base_url, "model": config.model},
        "personas": personas,
        "reviews_done": {}, "last_review": None, "current": None,
        "message": "Production plan queued. Nothing will be approved automatically.",
        "editorial_scan_id": None, "preflight": None,
    }
    _write(slug, record)
    _spawn(slug, record)
    return status(slug)


async def _worker(slug: str, job_id: str):
    try:
        while True:
            state = _load(slug)
            if not state or state["id"] != job_id or state["status"] not in ("queued", "running"):
                return
            _model(state)
            chapters = _chapters(slug)
            unfinished = [ch for ch in chapters if ch["status"] not in ("candidate", "approved")]
            if unfinished:
                state["phase"] = "draft"
                draft = book_jobs.status(slug)
                if draft.get("status") in ("queued", "running"):
                    state["status"] = "running"
                    state["message"] = "Waiting for the durable local Book Studio draft queue."
                    _write(slug, state)
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                if draft.get("status") == "paused" and state["status"] == "paused":
                    return
                if draft.get("status") in ("paused", "needs_attention", "interrupted"):
                    state["status"] = "needs_attention"
                    state["message"] = "The draft job requires author review: " + draft.get("message", "")
                    _write(slug, state)
                    return
                if book_jobs._next_pending(slug) is None:
                    state["status"] = "needs_attention"
                    state["message"] = "No retryable draft chapters remain; revise failed chapter briefs."
                    _write(slug, state)
                    return
                try:
                    book_jobs.start(slug, _model(state))
                except ValueError as exc:
                    state["status"] = "needs_attention"
                    state["message"] = "Could not start the drafting queue: " + str(exc)
                    _write(slug, state)
                    return
                state["status"] = "running"
                state["message"] = "Local book drafting started. New chapters remain candidates."
                _write(slug, state)
                await asyncio.sleep(POLL_SECONDS)
                continue

            next_review = _next_review(slug, state)
            if next_review:
                number, persona = next_review
                state["status"] = "running"
                state["phase"] = "reader_review"
                state["current"] = {"chapter": number, "persona": persona}
                state["message"] = f"Independent {persona.replace('_', ' ')} review of chapter {number}."
                _write(slug, state)
                version = _fingerprint(slug, number)
                try:
                    await book_reviews.evaluate(slug, number, persona, _model(state))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    newest = _load(slug)
                    if newest and newest["id"] == job_id:
                        newest["status"] = "needs_attention"
                        newest["current"] = None
                        newest["message"] = f"Reader {persona} for chapter {number} needs attention: {type(exc).__name__}: {str(exc)[:220]}"
                        _write(slug, newest)
                    return
                state = _load(slug)
                if not state or state["id"] != job_id:
                    return
                # Record completion only if the author hasn't edited the candidate.
                if _fingerprint(slug, number) == version:
                    state["reviews_done"][f"{number}:{persona}"] = version
                state["last_review"] = {"chapter": number, "persona": persona}
                state["current"] = None
                if state["status"] == "paused":
                    state["message"] = "Paused after the current reader evaluation."
                    _write(slug, state)
                    return
                state["message"] = f"Chapter {number} reader evaluation recorded for the author."
                _write(slug, state)
                await asyncio.sleep(0)
                continue

            state["current"] = None
            if any(ch["status"] != "approved" for ch in chapters):
                state["status"] = "awaiting_author"
                state["phase"] = "author_approval"
                state["message"] = (
                    "All available draft candidates and optional reader evaluations are ready. "
                    "Review, revise and explicitly approve each chapter in Book Studio. "
                    "Then choose Continue to run production checks."
                )
                _write(slug, state)
                return

            state["status"] = "running"
            state["phase"] = "editorial"
            state["message"] = "All chapters author-approved. Building whole-book editorial baseline."
            _write(slug, state)
            board = await asyncio.to_thread(editorial_board.scan, slug)
            state = _load(slug)
            if not state or state["id"] != job_id:
                return
            state["editorial_scan_id"] = board["scan_id"]
            state["phase"] = "preflight"
            state["message"] = "Reviewing publication readiness against the author-approved manuscript."
            _write(slug, state)
            readiness = await asyncio.to_thread(production_preflight.preflight, slug)
            state = _load(slug)
            if not state or state["id"] != job_id:
                return
            state["preflight"] = {
                "blockers": readiness["blockers"], "warnings": readiness["warnings"],
                "waived": readiness["waived"], "editorially_ready": readiness["editorially_ready"],
            }
            state["status"] = "completed"
            state["phase"] = "publishing_handoff"
            state["message"] = (
                "Production checks are complete. Review the Editorial Board and Production "
                "Readiness Gate in Publish. Exports remain an explicit author action."
            )
            _write(slug, state)
            return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        state = _load(slug)
        if state and state["id"] == job_id:
            state["status"] = "needs_attention"
            state["message"] = f"Production orchestration stopped: {type(exc).__name__}: {str(exc)[:220]}"
            _write(slug, state)
    finally:
        if _ACTIVE.get(slug) is asyncio.current_task():
            _ACTIVE.pop(slug, None)


def pause(slug: str) -> dict:
    state = _load(slug)
    if not state or state["status"] not in ("queued", "running"):
        raise ValueError("No active production conductor to pause")
    state["status"] = "paused"
    state["message"] = "Pause requested; active chapter generation or reader review may finish."
    _write(slug, state)
    draft = book_jobs.status(slug)
    if draft.get("status") in ("queued", "running"):
        book_jobs.pause(slug)
    return status(slug)


def resume(slug: str) -> dict:
    state = _load(slug)
    if not state or state["status"] not in ("paused", "needs_attention", "awaiting_author", "interrupted", "completed"):
        raise ValueError("No production run is ready to continue")
    if _running(slug):
        raise ValueError("The active production task is still finishing")
    _model(state)
    draft = book_jobs.status(slug)
    if draft.get("status") == "paused" and book_jobs._next_pending(slug):
        book_jobs.resume(slug)
    elif draft.get("status") == "needs_attention" and book_jobs._next_pending(slug):
        book_jobs.resume(slug)
    elif draft.get("status") in ("queued", "running") and not book_jobs._running(slug):
        raise ValueError("The book queue is not active yet; restore its service before continuing")
    state["status"] = "queued"
    state["message"] = "Resuming the author-led production workflow."
    state["preflight"] = None
    _write(slug, state)
    _spawn(slug, state)
    return status(slug)


async def recover_on_startup():
    for project in list_projects():
        slug = project["slug"]
        try:
            state = _load(slug)
            if not state or state["status"] not in ("queued", "running"):
                continue
            _model(state)
            state["status"] = "queued"
            state["message"] = "Production conductor resumed from its last checkpoint after service restart."
            _write(slug, state)
            _spawn(slug, state)
        except (OSError, ValueError, KeyError) as exc:
            try:
                state = _load(slug)
                if state:
                    state["status"] = "interrupted"
                    state["message"] = f"Recovery needs manual intervention: {str(exc)[:180]}"
                    _write(slug, state)
            except Exception:
                pass


async def stop_on_shutdown():
    tasks = [task for task in _ACTIVE.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _ACTIVE.clear()


def context_preview(slug: str, number: int) -> dict:
    state = book_studio.load_state(slug)
    if not state.get("configured") or not 1 <= number <= len(state["chapters"]):
        raise FileNotFoundError("Planned chapter does not exist")
    chapter = state["chapters"][number - 1]
    payload = book_studio._context(slug, state, number - 1)
    return {
        "number": number, "title": chapter["title"],
        "status": chapter["status"], "context": payload,
        "characters": len(payload), "budget": book_studio.MAX_CONTEXT,
        "source_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "disclaimer": (
            "This is the currently reconstructed context for the selected chapter, "
            "not a saved historical prompt. If the author changed canon or prior "
            "chapters since generation, the original model input may differ."
        ),
    }
