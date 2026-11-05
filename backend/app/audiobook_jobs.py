"""Restart-resumable, author-triggered offline whole-book narration.

Uses currently included Binder Draft docs in compile order. Each source
document is fingerprinted at job start; changing it pauses the job for the
author instead of silently narrating a different revision. No cloud TTS.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .audiobook_local import MAX_AUDIO_WORDS, _spoken_text, available_voices, render
from .publishing import compiled_documents
from .storage import get_project, list_projects, project_root, read_text

_TASKS: dict[str, asyncio.Task] = {}
MAX_BOOK_CHAPTERS = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "audiobook-batch.json"


def _read(slug: str) -> dict | None:
    path = _path(slug)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("chapters"), list) or not data.get("id"):
        raise ValueError("Audiobook job record is invalid")
    return data


def _write(slug: str, data: dict):
    path = _path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _active(slug: str) -> bool:
    task = _TASKS.get(slug)
    return bool(task and not task.done())


def status(slug: str) -> dict:
    record = _read(slug)
    if not record:
        return {"exists": False, "status": "idle", "active": False}
    return {
        **record, "exists": True, "active": _active(slug),
        "total": len(record["chapters"]),
        "completed": sum(ch.get("status") == "rendered" for ch in record["chapters"]),
    }


def _fingerprint(slug: str, path: str) -> str:
    return hashlib.sha256(read_text(slug, path).encode("utf-8")).hexdigest()


def _book(slug: str) -> list[dict]:
    documents = compiled_documents(slug)
    if not 1 <= len(documents) <= MAX_BOOK_CHAPTERS:
        raise ValueError("Select 1 to 120 manuscript documents in Binder > Draft")
    chapters = []
    for doc in documents:
        source = doc["path"]
        if not source.startswith("manuscript/") or not source.lower().endswith((".md", ".txt")):
            raise ValueError("Only manuscript Markdown/text documents can be narrated in batch")
        content = _spoken_text(doc["content"])
        words = len(content.split())
        if not 5 <= words <= MAX_AUDIO_WORDS:
            raise ValueError(f"Chapter {source} must contain 5 to {MAX_AUDIO_WORDS} narratable words")
        if content.strip() == f"Chapter 1\n\nBegin {get_project(slug)['name']} here.":
            raise ValueError("Replace the untouched welcome chapter before producing an audiobook")
        chapters.append({
            "path": source, "title": doc["title"], "fingerprint": _fingerprint(slug, source),
            "words": words, "status": "queued", "filename": "", "error": "",
        })
    return chapters


def start(slug: str, voice: str = "", rate: int = -1) -> dict:
    if sys.platform != "win32":
        raise ValueError("Offline Windows audiobook rendering is available on Windows only")
    if _active(slug):
        raise ValueError("An audiobook job is already active")
    current = _read(slug)
    if current and current["status"] in ("queued", "running"):
        raise ValueError("An audiobook job is already queued. Check its status.")
    if isinstance(rate, bool) or not isinstance(rate, int) or not -5 <= rate <= 5:
        raise ValueError("Narration speed must be an integer from -5 to 5")
    if voice and voice not in available_voices():
        raise ValueError("The selected offline voice is not installed")
    from .audio_production import snapshot
    config = snapshot(slug)
    # Freeze the author-selected voice and pronunciation dictionary for the
    # entire batch. Later edits require a new batch to avoid mixed editions.
    chapters = _book(slug)
    for chapter in chapters:
        profile = config["chapter_profiles"].get(chapter["path"], {})
        chapter["voice"] = profile.get("voice", voice)
        chapter["rate"] = profile.get("rate", rate)
    record = {
        "id": uuid4().hex, "status": "queued", "voice": voice, "rate": rate,
        "created_at": _now(), "updated_at": _now(),
        "chapters": chapters, "current": None,
        "pronunciations": config["pronunciations"], "chapter_casts": config.get("chapter_casts", {}),
        "settings_signature": config["signature"],
        "message": "Queued selected Binder chapters for local offline narration.",
    }
    _write(slug, record)
    _spawn(slug, record)
    return status(slug)


def _spawn(slug: str, record: dict):
    if _active(slug):
        raise ValueError("An audiobook job is already active")
    _TASKS[slug] = asyncio.create_task(_worker(slug, record["id"]), name=f"ember-audio-{slug}")


async def _worker(slug: str, job_id: str):
    try:
        while True:
            job = _read(slug)
            if not job or job["id"] != job_id or job["status"] not in ("queued", "running"):
                return
            chapter = next((ch for ch in job["chapters"] if ch["status"] != "rendered"), None)
            if chapter is None:
                job["status"] = "completed"
                job["current"] = None
                job["message"] = "All selected chapters narrated. Review the audio before distributing."
                _write(slug, job)
                return
            source = chapter["path"]
            try:
                actual = _fingerprint(slug, source)
                if actual != chapter["fingerprint"]:
                    raise ValueError(f"{source} changed since the audiobook job was queued. Start a new batch after reviewing edits.")
                from .audio_production import snapshot
                if job.get("settings_signature") and snapshot(slug)["signature"] != job["settings_signature"]:
                    raise ValueError("Narration dictionary or chapter profiles changed since this batch started. Create a new batch.")
                job["status"] = "running"
                job["current"] = source
                job["message"] = f"Narrating {source} offline."
                _write(slug, job)
                from .local_resources import reservation
                async with reservation():
                    speed = chapter.get("rate", job.get("rate", -1))
                    selected_voice = chapter.get("voice", job["voice"])
                    custom = job.get("pronunciations", []) or bool(job.get("chapter_casts", {}).get(source)) or chapter.get("rate", job.get("rate", -1)) != job.get("rate", -1) or chapter.get("voice", job["voice"]) != job["voice"]
                    if custom:
                        rendered = await asyncio.to_thread(
                            render, slug, source, selected_voice, speed,
                            rules=job.get("pronunciations", []),
                            settings_signature=job["settings_signature"],
                            casts=job.get("chapter_casts", {}).get(source, []),
                        )
                    elif speed == -1:
                        rendered = await asyncio.to_thread(render, slug, source, selected_voice)
                    else:
                        rendered = await asyncio.to_thread(render, slug, source, selected_voice, speed)
                # An author may have changed the chapter while TTS was speaking.
                if _fingerprint(slug, source) != chapter["fingerprint"]:
                    raise ValueError(f"{source} changed while narration was in progress; review the output.")
                if job.get("settings_signature") and snapshot(slug)["signature"] != job["settings_signature"]:
                    raise ValueError("Narration settings changed while a chapter was rendering; create a new batch.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                latest = _read(slug)
                if latest and latest["id"] == job_id:
                    latest["status"] = "needs_attention"
                    latest["current"] = None
                    latest["message"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                    _write(slug, latest)
                return
            latest = _read(slug)
            if not latest or latest["id"] != job_id:
                return
            current = next((ch for ch in latest["chapters"] if ch["path"] == source), None)
            if current:
                current["status"] = "rendered"
                current["filename"] = rendered["filename"]
            latest["current"] = None
            latest["message"] = f"Narrated {source}."
            _write(slug, latest)
            if latest["status"] == "paused":
                latest["message"] = f"Paused after completing {source}."
                _write(slug, latest)
                return
            await asyncio.sleep(0)
    finally:
        if _TASKS.get(slug) is asyncio.current_task():
            _TASKS.pop(slug, None)


def pause(slug: str) -> dict:
    job = _read(slug)
    if not job or job["status"] not in ("queued", "running"):
        raise ValueError("No audiobook batch is running")
    job["status"] = "paused"
    job["message"] = "Pause requested: current chapter may finish first."
    _write(slug, job)
    return status(slug)


def resume(slug: str) -> dict:
    job = _read(slug)
    if not job or job["status"] not in ("paused", "interrupted", "needs_attention"):
        raise ValueError("No paused or interrupted audiobook job")
    if _active(slug):
        raise ValueError("Current narration is still finishing")
    if not any(ch["status"] != "rendered" for ch in job["chapters"]):
        raise ValueError("All audiobook chapters have already been rendered")
    job["status"] = "queued"
    job["message"] = "Audiobook job resumed."
    _write(slug, job)
    _spawn(slug, job)
    return status(slug)


async def recover_on_startup():
    for project in list_projects():
        slug = project["slug"]
        try:
            job = _read(slug)
            if not job or job["status"] not in ("queued", "running"):
                continue
            if _active(slug):
                continue
            job["status"] = "queued"
            job["message"] = "Audiobook batch resumed after server restart."
            _write(slug, job)
            _spawn(slug, job)
        except (OSError, ValueError, KeyError) as exc:
            try:
                job = _read(slug)
                if job:
                    job["status"] = "interrupted"
                    job["message"] = str(exc)[:250]
                    _write(slug, job)
            except Exception:
                pass


async def stop_on_shutdown():
    tasks = [task for task in _TASKS.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _TASKS.clear()


def _hash_audio_file(path: Path) -> str:
    """Hash a large WAV or MP3 without loading the entire recording into RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def batch_archive(slug: str) -> Path:
    """Package exactly this completed Binder-ordered batch, not older tracks."""
    import zipfile
    from .audiobook_local import audio_file

    job = _read(slug)
    if not job or job["status"] != "completed":
        raise ValueError("Finish the whole-book narration before exporting its batch package")
    entries = job["chapters"]
    from .audio_production import snapshot, load as production_settings
    if job.get("settings_signature") and snapshot(slug)["signature"] != job["settings_signature"]:
        raise ValueError("Narration dictionary or chapter narrator settings changed since this batch. Re-render before export.")
    notes = production_settings(slug)["proof_notes"]
    from .proof_approval import proof_status
    for chapter in entries:
        if _fingerprint(slug, chapter["path"]) != chapter["fingerprint"]:
            raise ValueError(f"{chapter['path']} changed since narration. Re-render the new manuscript before exporting.")
        if any(note["path"] == chapter["path"] and note["filename"] == chapter["filename"]
               and note["status"] == "open" for note in notes):
            raise ValueError(f"{chapter['path']} has unresolved proof-listening notes; review before exporting.")
        if not proof_status(slug, chapter["path"], chapter["filename"])["approved"]:
            raise ValueError(f"{chapter['path']} requires author proof-listening approval before exporting.")
    if not entries or any(ch.get("status") != "rendered" for ch in entries):
        raise ValueError("All selected chapters must be rendered before batch export")
    target = project_root(slug) / ".ember" / "audiobook" / "current-book-narration.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_suffix(".zip.tmp")
    manifest = {
        "job_id": job["id"], "voice": job["voice"] or "system-default",
        "rate": job.get("rate", -1),
        "chapters": [],
        "note": "Local single-narrator chapter audio; not professionally mastered.",
    }
    with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_STORED) as output:
        for index, chapter in enumerate(entries, 1):
            path = audio_file(slug, chapter["filename"])
            extension = path.suffix.lower()
            name = f"{index:03d}-chapter{extension}"
            output.write(path, arcname=name)
            manifest["chapters"].append({
                "index": index, "path": chapter["path"], "filename": name,
                "sha256": _hash_audio_file(path),
            })
        output.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    staging.replace(target)
    return target
