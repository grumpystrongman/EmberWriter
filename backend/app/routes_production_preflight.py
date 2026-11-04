"""Project-scoped editorial production preflight. Advisory, never publishing lock."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .production_preflight import markdown, preflight, restore, waive

router = APIRouter(prefix="/api/projects/{slug}/production-preflight", tags=["Production Preflight"])


class WaiverRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=1200)


def _error(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("")
def check(slug: str) -> dict:
    try:
        return preflight(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/report.md", response_class=PlainTextResponse)
def report(slug: str) -> str:
    try:
        return markdown(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/waivers/{issue_id}")
def create_waiver(slug: str, issue_id: str, request: WaiverRequest) -> dict:
    try:
        return waive(slug, issue_id, request.reason)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.delete("/waivers/{issue_id}")
def remove_waiver(slug: str, issue_id: str) -> dict:
    try:
        return restore(slug, issue_id)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
