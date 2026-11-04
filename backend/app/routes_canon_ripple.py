"""Project-scoped canon change review API."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .canon_ripple import create_ripple, list_ripples, update_ripple

router = APIRouter(prefix="/api/projects/{slug}/canon-ripples", tags=["Canon Ripple"])


class CanonProposal(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    old_fact: str = Field(min_length=3, max_length=500)
    proposed_fact: str = Field(min_length=1, max_length=500)
    source_path: str = Field(default="", max_length=500)
    rationale: str = Field(default="", max_length=2000)


class CanonAction(BaseModel):
    action: Literal["approve", "reject", "mark_reviewed", "reopen_impact", "resolve", "rescan"]
    path: str = Field(default="", max_length=500)


@router.get("")
def get_ledger(slug: str) -> list[dict]:
    try:
        return list_ripples(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("", status_code=201)
def new_proposal(slug: str, payload: CanonProposal) -> dict:
    try:
        return create_ripple(slug, **payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{ripple_id}/actions")
def action(slug: str, ripple_id: str, payload: CanonAction) -> dict:
    try:
        return update_ripple(slug, ripple_id, **payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
