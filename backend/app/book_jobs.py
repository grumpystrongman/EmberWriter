"""Durable, local-only drafting conductor.

The author opts in per project. The job record is stored under that project's
.ember folder and never contains manuscript text or credentials. After an app
restart an opted-in running/queued job can be resumed by startup recovery.
A pause finishes the current chapter before stopping. No chapter is approved
or published automatically.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .book_studio import _local_model, draft_next, load_state
from .models import ProviderConfig
from .storage import get_project, list_projects, project_root

_TASKS: dict[str, asyncio.Task] = {}
MAX_CHAPTERS_PER_RUN = 80


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "book-job.json"


def _write(slug: str, job: dict) -> dict:
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    job["updated_at"] = _now()
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return job


def _load(slug: str) -> dict | None:
    path = _path(slug)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("id") or not isinstance(data.get("provider"), dict):
        raise ValueError("Invalid local book job record")
    return data


def _running(slug: str) -> bool:
    task = _TASKS.get(slug)
    return bool(task and not task.done())


def status(slug: str) -> dict:
    job = _load(slug)
    if job is None:
        return {"exists": False, "status": "idle", "active": False}
    # Do not expose the provider internals. Model tag is safe to show.
    result = {key: value for key, value in job.items() if key != "provider"}
    result["exists"] = True
    result["active"] = _running(slug)
    result["model"] = job["provider"].get("model", "")
    # Persisted "running" means resumed when the service starts, not
    # necessarily that a task is currently executing during a unit test.
    chapters = load_state(slug).get("chapters", [])
    result["total_chapters"] = len(chapters)
    result["drafted"] = sum(ch.get("status") in ("candidate", "approved") for ch in chapters)
    result["approved"] = sum(ch.get("status") == "approved" for ch in chapters)
    return result


def _next_pending(slug: str) -> dict | None:
    chapters = load_state(slug).get("chapters", [])
    for ch in chapters:
        if ch.get("status") == "planned" or (
            ch.get("status") == "failed" and ch.get("attempts", 0) < 3
        ):
            return ch
    return None


async def _worker(slug: str, job_id: str) -> None:
    """One worker per project; each chapter generation is safely checkpointed."""
    try:
        for _ in range(MAX_CHAPTERS_PER_RUN):
            job = _load(slug)
            if job is None or job.get("id") != job_id:
                return
            if job["status"] not in ("queued", "running"):
                return
            chapter = _next_pending(slug)
            if chapter is None:
                # Exhausted failures cannot be silently treated as a finished book.
                chapters = load_state(slug).get("chapters", [])
                exhausted = [
                    ch for ch in chapters if ch.get("status") == "failed"
                    and ch.get("attempts", 0) >= 3
                ]
                incomplete = [ch for ch in chapters if ch.get("status") not in ("candidate", "approved")]
                job["status"] = "needs_attention" if incomplete else "completed"
                job["message"] = (
                    "A chapter exhausted three attempts. Revise its brief to retry."
                    if exhausted else ("A chapter is unfinished; check its state before continuing."
                                       if incomplete else "Every planned chapter has a reviewable candidate or author approval.")
                )
                _write(slug, job)
                return
            job["status"] = "running"
            job["current_chapter"] = chapter["number"]
            job["message"] = f"Drafting chapter {chapter['number']}."
            _write(slug, job)
            try:
                await draft_next(slug, ProviderConfig.model_validate(job["provider"]))
            except asyncio.CancelledError:
                # Leave 'running' persisted so startup can recover after restart.
                raise
            except Exception as exc:
                job = _load(slug)
                if job and job.get("id") == job_id:
                    job["status"] = "needs_attention"
                    job["message"] = (
                        f"Chapter {chapter['number']} needs attention: "
                        f"{type(exc).__name__}: {str(exc)[:250]}"
                    )
                    job["current_chapter"] = None
                    _write(slug, job)
                return
            # Do not overwrite a pause requested while the LLM was generating.
            job = _load(slug)
            if job is None or job.get("id") != job_id:
                return
            job["completed_in_run"] = int(job.get("completed_in_run", 0)) + 1
            job["current_chapter"] = None
            if job["status"] == "paused":
                job["message"] = "Paused after finishing the current chapter."
                _write(slug, job)
                return
            job["message"] = f"Chapter {chapter['number']} saved for author review."
            _write(slug, job)
            await asyncio.sleep(0)
        # Defensive upper bound; typical plans have <= 80 chapters.
        job = _load(slug)
        if job and job.get("id") == job_id and job["status"] == "running":
            job["status"] = "needs_attention"
            job["message"] = "This run reached its chapter limit. Resume to continue."
            _write(slug, job)
    finally:
        # Keep task cleanup async-loop local. Do not reset 'running' on abrupt
        # cancellation; startup recovery is responsible for resuming.
        current = asyncio.current_task()
        if _TASKS.get(slug) is current:
            _TASKS.pop(slug, None)


def _start_task(slug: str, job: dict) -> None:
    if _running(slug):
        raise ValueError("A book job is already running for this project")
    _TASKS[slug] = asyncio.create_task(
        _worker(slug, job["id"]), name=f"book-studio-{slug}"
    )


def start(slug: str, config: ProviderConfig) -> dict:
    _local_model(config)
    state = load_state(slug)
    if not state.get("configured"):
        raise ValueError("Create a book plan before starting a draft run")
    if _next_pending(slug) is None:
        raise ValueError("There are no remaining draftable chapters")
    if _running(slug):
        raise ValueError("A book job is already running")
    existing = _load(slug)
    if existing and existing.get("status") in ("queued", "running"):
        raise ValueError("A book job is already queued; reload its status")
    job = {
        "id": uuid4().hex, "status": "queued", "created_at": _now(),
        "updated_at": _now(), "provider": {
            "provider": "ollama", "base_url": config.base_url, "model": config.model,
        },
        "current_chapter": None, "completed_in_run": 0,
        "message": "Queued for local generation. Drafts remain unapproved."
    }
    _write(slug, job)
    _start_task(slug, job)
    return status(slug)


def pause(slug: str) -> dict:
    job = _load(slug)
    if not job or job["status"] not in ("running", "queued"):
        raise ValueError("No active book job to pause")
    job["status"] = "paused"
    job["message"] = "Pause requested; current chapter may finish before stopping."
    _write(slug, job)
    return status(slug)


def resume(slug: str) -> dict:
    job = _load(slug)
    if not job or job["status"] not in ("paused", "needs_attention", "interrupted"):
        raise ValueError("No paused or interrupted book job to resume")
    if _running(slug):
        raise ValueError("Book generation is still finishing; try again after it stops")
    _local_model(ProviderConfig.model_validate(job["provider"]))
    if _next_pending(slug) is None:
        raise ValueError("No retryable chapters left; edit the chapter brief or review existing candidates")
    job["status"] = "queued"
    job["message"] = "Resumed local drafting."
    _write(slug, job)
    _start_task(slug, job)
    return status(slug)


async def recover_on_startup() -> None:
    """Requeue explicitly authorized running jobs, never paused ones."""
    for project in list_projects():
        slug = project["slug"]
        try:
            job = _load(slug)
            if job is None or job.get("status") not in ("queued", "running"):
                continue
            _local_model(ProviderConfig.model_validate(job["provider"]))
            # Chapter status from an interrupted process becomes failed and
            # retryable, never changes an author-approved chapter.
            if _next_pending(slug) is None:
                job["status"] = "needs_attention"
                job["message"] = "No retryable chapter remains after restart."
                _write(slug, job)
                continue
            job["status"] = "queued"
            job["message"] = "Restored after server restart; resuming locally."
            _write(slug, job)
            _start_task(slug, job)
        except (OSError, ValueError, KeyError) as exc:
            # Don't prevent the whole server from starting if a job is corrupt.
            try:
                job = _load(slug)
                if job:
                    job["status"] = "interrupted"
                    job["message"] = f"Recovery needs manual review: {str(exc)[:180]}"
                    _write(slug, job)
            except Exception:
                pass


async def stop_on_shutdown() -> None:
    tasks = [task for task in _TASKS.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _TASKS.clear()
