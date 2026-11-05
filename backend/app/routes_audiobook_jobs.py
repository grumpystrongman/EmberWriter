"""Whole-book offline audiobook job endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audiobook_jobs import batch_archive, pause, resume, start, status

router = APIRouter(prefix="/api/projects/{slug}/audiobook-jobs", tags=["Audiobook Jobs"])


class StartNarration(BaseModel):
    voice: str = Field(default="", max_length=110)
    rate: int = Field(default=-1, ge=-5, le=5)


def _error(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, (ValueError, OSError)):
        raise HTTPException(409, str(exc)) from exc
    raise exc


@router.get("")
def job_status(slug: str) -> dict:
    try:
        return status(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/start", status_code=202)
async def start_job(slug: str, payload: StartNarration) -> dict:
    try:
        return start(slug, payload.voice, payload.rate)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/pause")
def pause_job(slug: str) -> dict:
    try:
        return pause(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/resume", status_code=202)
async def resume_job(slug: str) -> dict:
    try:
        return resume(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/quality")
def narration_quality(slug: str) -> dict:
    from .audiobook_quality import inspect
    try:
        return inspect(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/mastering")
async def mastering_report(slug: str) -> dict:
    import asyncio
    from .audio_mastering import report
    from .local_resources import reservation
    try:
        async with reservation():
            return await asyncio.to_thread(report, slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/export.m4b")
def book_m4b(slug: str) -> FileResponse:
    import subprocess
    from .audiobook_m4b import export_m4b
    try:
        path = export_m4b(slug)
        return FileResponse(path, filename="emberwriter-whole-book-audiobook.m4b",
                            media_type="audio/mp4")
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(502, "Local FFmpeg could not complete M4B encoding") from exc


@router.get("/export-leveled.m4b")
async def leveled_book_m4b(slug: str) -> FileResponse:
    import asyncio
    import subprocess
    from .audiobook_m4b import export_m4b
    from .local_resources import reservation
    try:
        async with reservation():
            path = await asyncio.to_thread(export_m4b, slug, level=True)
        return FileResponse(path, filename="emberwriter-whole-book-leveled.m4b",
                            media_type="audio/mp4")
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(502, "Local FFmpeg loudness leveling failed") from exc


@router.get("/export")
def book_archive(slug: str) -> FileResponse:
    try:
        path = batch_archive(slug)
        return FileResponse(path, filename="emberwriter-whole-book-audiobook.zip", media_type="application/zip")
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/retailer/acx-preflight")
async def acx_preflight(slug: str) -> dict:
    """Strict preflight of ACX technical limits; never claim approval."""
    import asyncio
    from .audio_retailer import report
    from .local_resources import reservation
    try:
        async with reservation():
            return await asyncio.to_thread(report, slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)
