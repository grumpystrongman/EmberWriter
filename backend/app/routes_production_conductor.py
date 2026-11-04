"""Opt-in author-led whole-book production pipeline API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import ProviderConfig
from .production_conductor import context_preview, pause, resume, start, status

router = APIRouter(prefix="/api/projects/{slug}/production-conductor", tags=["Production Conductor"])


class ProductionStart(BaseModel):
    provider: ProviderConfig
    personas: list[str] = Field(default_factory=lambda: ["developmental_editor", "line_editor"],
                                max_length=3)


def _failure(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(409, str(exc)) from exc


@router.get("")
def current_status(slug: str) -> dict:
    try:
        return status(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.get("/context/{number}")
def inspect_context(slug: str, number: int) -> dict:
    try:
        return context_preview(slug, number)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.post("/start", status_code=202)
async def begin(slug: str, payload: ProductionStart) -> dict:
    try:
        return start(slug, payload.provider, payload.personas)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.post("/pause")
def halt(slug: str) -> dict:
    try:
        return pause(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.post("/continue", status_code=202)
async def continue_workflow(slug: str) -> dict:
    try:
        return resume(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)
