"""Sentence-level local grammar and prose choices. Exact source validation."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .prose_editor import analyze, decide, sources

router = APIRouter(prefix="/api/projects/{slug}/prose-editor", tags=["Prose Editor"])


class Inspection(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    perspective: str = Field(default="unspecified", pattern="^(unspecified|first|third)$")
    tense: str = Field(default="unspecified", pattern="^(unspecified|past|present)$")


class Decision(Inspection):
    finding_id: str = Field(min_length=10, max_length=64)
    source_hash: str = Field(min_length=64, max_length=64)
    action: str = Field(pattern="^(dismiss|reopen|apply)$")
    reason: str = Field(default="", max_length=500)


def _fail(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(409, str(exc)) from exc


@router.get("/chapters")
def chapters(slug: str) -> list[dict]:
    try:
        return sources(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/inspect")
def inspect(slug: str, payload: Inspection) -> dict:
    try:
        return analyze(slug, payload.path, payload.perspective, payload.tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/decision")
def record(slug: str, payload: Decision) -> dict:
    try:
        return decide(slug, payload.path, payload.finding_id, payload.source_hash,
                      payload.action, payload.perspective, payload.tense, payload.reason)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)
