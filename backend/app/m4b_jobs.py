"""Restart-recoverable, author-triggered M4B encode orchestration.

The encoding request returns immediately. A server-restart reruns a whole
interrupted encode from verified inputs; no incomplete output is published.
Single-server-process scheduling only. No uploads or hosted services.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .storage import get_project, list_projects, project_root

_TASKS: dict[str, asyncio.Task] = {}
_CANCEL: dict[str, threading.Event] = {}
STAGES = ("queued", "measuring", "encoding", "verifying", "completed", "interrupted", "needs_attention", "paused")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "m4b-encode-job.json"


def _read(slug: str) -> dict | None:
    path = _path(slug)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("status") not in STAGES or data.get("mode") not in ("original", "leveled") or not data.get("id"):
        raise ValueError("Invalid saved M4B encode job")
    return data


def _write(slug: str, record: dict):
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    record["updated_at"] = _now()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _active(slug: str) -> bool:
    task = _TASKS.get(slug)
    return bool(task is not None and not task.done())


def status(slug: str) -> dict:
    item = _read(slug)
    if not item:
        return {"exists": False, "status": "idle", "active": False}
    return {**item, "exists": True, "active": _active(slug),
            "downloadable": item["status"] == "completed"}


def _spawn(slug: str, record: dict):
    if _active(slug):
        raise ValueError("A M4B encode is already active for this project")
    _TASKS[slug] = asyncio.create_task(_worker(slug, record["id"]), name=f"ember-m4b-{slug}")


def _identity(slug: str) -> str:
    """Fingerprint this exact narration batch and *actual audio file bytes*.

    A completed M4B may not be downloaded as current if a source track has
    been replaced with different audio while keeping its valid WAV header.
    """
    from .audiobook_jobs import _read as read_audio, _fingerprint, _hash_audio_file
    from .audiobook_local import audio_file
    job = read_audio(slug)
    if not job or job.get("status") != "completed":
        raise ValueError("A completed narration batch is required for M4B")
    digest = hashlib.sha256()
    digest.update(job["id"].encode("ascii"))
    for item in job["chapters"]:
        if _fingerprint(slug, item["path"]) != item["fingerprint"]:
            raise ValueError("Manuscript changed since narration")
        digest.update(item["path"].encode("utf-8"))
        digest.update(item["filename"].encode("ascii"))
        digest.update(_hash_audio_file(audio_file(slug, item["filename"])).encode("ascii"))
    return digest.hexdigest()


def start(slug: str, mode: str = "original") -> dict:
    if mode not in ("original", "leveled"):
        raise ValueError("Choose original or leveled audiobook")
    if _active(slug):
        raise ValueError("An M4B encode is already running")
    current = _read(slug)
    if current and current["status"] in ("queued", "measuring", "encoding", "verifying"):
        raise ValueError("An M4B encode is already queued; check its status")
    from .audiobook_quality import inspect
    if not inspect(slug)["ready"]:
        raise ValueError("Complete and verify the current audiobook before encoding")
    record = {
        "id": uuid4().hex, "mode": mode, "status": "queued",
        "created_at": _now(), "message": "Waiting for local audio encode resources.",
        "filename": "", "updated_at": _now(), "input_identity": _identity(slug),
    }
    _write(slug, record)
    _spawn(slug, record)
    return status(slug)


def pause(slug: str) -> dict:
    record = _read(slug)
    if not record or record["status"] != "queued":
        raise ValueError("M4B may only be paused before encoding starts")
    record["status"] = "paused"
    record["message"] = "Paused before encoding."
    _write(slug, record)
    return status(slug)


def resume(slug: str) -> dict:
    if _active(slug):
        raise ValueError("Encoding is still finishing")
    record = _read(slug)
    if not record or record["status"] not in ("paused", "interrupted", "needs_attention"):
        raise ValueError("No paused or recoverable M4B job")
    from .audiobook_quality import inspect
    if not inspect(slug)["ready"]:
        raise ValueError("The audiobook has changed or needs attention; verify before retrying")
    record["status"] = "queued"
    record["message"] = "Retrying the complete M4B encode from verified local audio."
    record["filename"] = ""
    if _identity(slug) != record.get("input_identity"):
        raise ValueError("Narration inputs changed since the saved encode; start a new encode job")
    _write(slug, record)
    _spawn(slug, record)
    return status(slug)


async def _worker(slug: str, job_id: str):
    from .audiobook_m4b import export_m4b
    from .local_resources import reservation
    cancel_event = threading.Event()
    _CANCEL[slug] = cancel_event
    loop = asyncio.get_running_loop()
    def stage(value: str):
        def update():
            record = _read(slug)
            if record and record["id"] == job_id and record["status"] not in ("paused", "interrupted", "completed", "needs_attention"):
                record["status"] = value
                record["message"] = {
                    "measuring": "Measuring complete-book loudness for optional leveling.",
                    "encoding": "Encoding the chapter-marked audiobook locally.",
                    "verifying": "Checking AAC output, chapters and source freshness.",
                }.get(value, value)
                _write(slug, record)
        loop.call_soon_threadsafe(update)
    try:
        record = _read(slug)
        if not record or record["id"] != job_id or record["status"] != "queued":
            return
        async with reservation():
            record = _read(slug)
            if not record or record["id"] != job_id or record["status"] != "queued":
                return
            if record.get("input_identity") != _identity(slug):
                raise ValueError("Narration inputs changed while the M4B job was queued")
            future = asyncio.create_task(asyncio.to_thread(
                export_m4b, slug, level=record["mode"] == "leveled",
                cancel_event=cancel_event, progress=stage,
            ))
            try:
                target = await asyncio.shield(future)
            except asyncio.CancelledError:
                cancel_event.set()
                try:
                    await asyncio.shield(future)
                except Exception:
                    pass
                raise
        if record.get("input_identity") != _identity(slug):
            raise ValueError("Narration inputs changed during encoding; re-encode current audio")
        from .audiobook_jobs import _hash_audio_file
        latest = _read(slug)
        if latest and latest["id"] == job_id:
            latest["artifact_sha256"] = _hash_audio_file(target)
            latest["status"] = "completed"
            latest["filename"] = target.name
            latest["message"] = "M4B is ready. Listen before distribution."
            _write(slug, latest)
    except asyncio.CancelledError:
        latest = _read(slug)
        if latest and latest["id"] == job_id and latest["status"] not in ("completed", "paused"):
            latest["status"] = "interrupted"
            latest["message"] = "Encoding interrupted; resume to reverify and encode again."
            _write(slug, latest)
        raise
    except Exception as exc:
        latest = _read(slug)
        if latest and latest["id"] == job_id:
            latest["status"] = "needs_attention"
            latest["filename"] = ""
            latest["message"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            _write(slug, latest)
    finally:
        _CANCEL.pop(slug, None)
        if _TASKS.get(slug) is asyncio.current_task():
            _TASKS.pop(slug, None)


async def recover_on_startup():
    for project in list_projects():
        slug = project["slug"]
        try:
            record = _read(slug)
            if not record or record["status"] not in ("queued", "measuring", "encoding", "verifying"):
                continue
            if _active(slug):
                continue
            record["status"] = "queued"
            record["message"] = "Restarted: checking the current audio before encoding again."
            _write(slug, record)
            _spawn(slug, record)
        except (OSError, ValueError, KeyError):
            continue


async def stop_on_shutdown():
    tasks = [task for task in _TASKS.values() if not task.done()]
    for event in _CANCEL.values():
        event.set()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _TASKS.clear()
    _CANCEL.clear()
