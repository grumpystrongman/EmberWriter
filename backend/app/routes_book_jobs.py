"""Project-scoped background book run API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .book_jobs import pause, resume, start, status
from .models import ProviderConfig

router = APIRouter(prefix="/api/projects/{slug}/book-jobs", tags=["Book Studio Jobs"])


class StartJob(BaseModel):
    provider: ProviderConfig


@router.get("")
def job_status(slug: str) -> dict:
    try:
        return status(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/start", status_code=202)
async def begin(slug: str, request: StartJob) -> dict:
    try:
        return start(slug, request.provider)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/pause")
def pause_job(slug: str) -> dict:
    try:
        return pause(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/resume", status_code=202)
async def resume_job(slug: str) -> dict:
    try:
        return resume(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc
