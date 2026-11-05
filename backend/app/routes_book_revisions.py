"""Reviewable, author-controlled chapter revisions, using local generation only."""
import asyncio

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .book_revisions import decide, get_proposal, list_proposals, propose
from .models import ProviderConfig

router = APIRouter(prefix="/api/projects/{slug}/book-revisions", tags=["Book Revisions"])


class RevisionRequest(BaseModel):
    provider: ProviderConfig
    author_direction: str = Field(default="", max_length=2000)


class DecisionRequest(BaseModel):
    action: str = Field(pattern="^(accept|reject)$")


def _error(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, (OSError, ValueError)):
        raise HTTPException(400, str(exc)) from exc
    if isinstance(exc, (httpx.HTTPError, RuntimeError, asyncio.TimeoutError)):
        raise HTTPException(502, str(exc)[:400]) from exc
    raise exc


@router.get("/{number}")
def history(slug: str, number: int) -> dict:
    try:
        return list_proposals(slug, number)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)


@router.post("/{number}/propose", status_code=201)
async def draft_revision(slug: str, number: int, payload: RevisionRequest) -> dict:
    try:
        return await propose(slug, number, payload.provider, payload.author_direction)
    except (TimeoutError, FileNotFoundError, ValueError, OSError, httpx.HTTPError, RuntimeError) as exc:
        _error(exc)


@router.get("/{number}/{proposal_id}")
def preview(slug: str, number: int, proposal_id: str) -> dict:
    try:
        return get_proposal(slug, number, proposal_id)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/{number}/{proposal_id}/decision")
def decision(slug: str, number: int, proposal_id: str, payload: DecisionRequest) -> dict:
    try:
        return decide(slug, number, proposal_id, payload.action)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
