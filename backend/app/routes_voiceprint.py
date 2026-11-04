"""Offline, project-local author voice and rhythm comparison."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .voiceprint_lab import baseline, options, report, select

router = APIRouter(prefix="/api/projects/{slug}/voiceprint", tags=["Voiceprint Lab"])


class ReferenceSelection(BaseModel):
    path: str = Field(min_length=1, max_length=500)


def _error(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("/options")
def references(slug: str) -> list[dict]:
    try:
        return options(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/reference")
def selected_reference(slug: str) -> dict:
    try:
        return baseline(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.put("/reference")
def set_reference(slug: str, payload: ReferenceSelection) -> dict:
    try:
        return select(slug, payload.path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/report")
def comparison(slug: str) -> dict:
    try:
        return report(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
