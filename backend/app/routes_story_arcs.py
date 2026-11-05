"""Opt-in narrative arc inspection; evidence-backed and author-controlled."""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .models import ProviderConfig
from .story_arc_investigator import act, chapters, dossier, dossier_markdown, inspect, overview

router = APIRouter(prefix="/api/projects/{slug}/story-arcs", tags=["Story Arc Investigator"])


class Inspection(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    provider: ProviderConfig
    focus: str = Field(default="", max_length=1000)


class ArcAction(BaseModel):
    action: str = Field(pattern="^(accept|dismiss|reopen|track_promise)$")


def _bad(error):
    if isinstance(error, FileNotFoundError):
        raise HTTPException(404, str(error)) from error
    if isinstance(error, (ValueError, OSError)):
        raise HTTPException(400, str(error)) from error
    raise HTTPException(502, str(error)[:400]) from error


@router.get("")
def dashboard(slug: str) -> dict:
    try:
        return overview(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _bad(exc)


@router.get("/chapters")
def available(slug: str) -> list[dict]:
    try:
        return chapters(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _bad(exc)


@router.get("/dossier")
def narrative_dossier(slug: str) -> dict:
    try:
        return dossier(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _bad(exc)


@router.get("/dossier.md", response_class=PlainTextResponse)
def narrative_dossier_markdown(slug: str) -> str:
    try:
        return dossier_markdown(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _bad(exc)


@router.post("/inspect", status_code=201)
async def analyze_chapter(slug: str, payload: Inspection) -> dict:
    try:
        return await inspect(slug, payload.path, payload.provider, payload.focus)
    except (TimeoutError, FileNotFoundError, ValueError, OSError, httpx.HTTPError, RuntimeError) as exc:
        _bad(exc)


@router.post("/{analysis_id}/events/{event_id}")
def event_action(slug: str, analysis_id: str, event_id: str, payload: ArcAction) -> dict:
    try:
        return act(slug, analysis_id, event_id, payload.action)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _bad(exc)
