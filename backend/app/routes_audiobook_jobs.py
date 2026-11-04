"""Whole-book offline audiobook job endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audiobook_jobs import batch_archive, pause, resume, start, status

router = APIRouter(prefix="/api/projects/{slug}/audiobook-jobs", tags=["Audiobook Jobs"])


class StartNarration(BaseModel):
    voice: str = Field(default="", max_length=110)


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
        return start(slug, payload.voice)
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


@router.get("/export")
def book_archive(slug: str) -> FileResponse:
    try:
        path = batch_archive(slug)
        return FileResponse(path, filename="emberwriter-whole-book-audiobook.zip", media_type="application/zip")
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
