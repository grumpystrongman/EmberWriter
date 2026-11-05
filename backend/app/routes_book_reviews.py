"""Project-local evidence-backed reader panel review API."""
import asyncio

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .book_reviews import PERSONAS, brief, decide, evaluate, history
from .models import ProviderConfig

router = APIRouter(prefix="/api/projects/{slug}/book-reviews", tags=["Book Reviews"])


class EvaluateRequest(BaseModel):
    persona: str = Field(max_length=40)
    provider: ProviderConfig
    focus: str = Field(default="", max_length=1000)


class DecisionRequest(BaseModel):
    action: str = Field(max_length=10)
    author_note: str = Field(default="", max_length=1400)


def _failure(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, (ValueError, OSError)):
        raise HTTPException(400, str(exc)) from exc
    if isinstance(exc, (httpx.HTTPError, RuntimeError, asyncio.TimeoutError)):
        raise HTTPException(502, str(exc)[:350]) from exc
    raise exc


@router.get("/personas")
def personas() -> list[dict]:
    return [{"id": key, "name": label, "lens": lens} for key, (label, lens) in PERSONAS.items()]


@router.get("/{number}")
def read(slug: str, number: int) -> dict:
    try:
        return history(slug, number)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.post("/{number}/evaluate")
async def analyze(slug: str, number: int, payload: EvaluateRequest) -> dict:
    try:
        return await evaluate(slug, number, payload.persona, payload.provider, payload.focus)
    except (TimeoutError, FileNotFoundError, ValueError, OSError, httpx.HTTPError, RuntimeError) as exc:
        _failure(exc)


@router.post("/{number}/{review_id}/findings/{finding_id}")
def record_decision(slug: str, number: int, review_id: str, finding_id: str,
                    payload: DecisionRequest) -> dict:
    try:
        return decide(slug, number, review_id, finding_id, payload.action, payload.author_note)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)


@router.get("/{number}/revision-brief")
def get_brief(slug: str, number: int) -> dict:
    try:
        return brief(slug, number)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _failure(exc)
