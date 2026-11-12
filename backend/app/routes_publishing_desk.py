"""Local publishing command deck; explicit, version-bound author release receipts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .publishing_desk import report, signoff

router = APIRouter(prefix="/api/projects/{slug}/publishing-desk", tags=["Publishing Desk"])


class ReviewReceipt(BaseModel):
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    note: str = Field(min_length=12, max_length=1200)
    acknowledged: bool = False


def _error(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, detail=str(exc)) from exc
    if "changed since review" in str(exc):
        raise HTTPException(409, detail=str(exc)) from exc
    raise HTTPException(400, detail=str(exc)) from exc


@router.get("")
def dashboard(slug: str) -> dict:
    try:
        return report(slug)
    except (ValueError, OSError, FileNotFoundError, TypeError) as exc:
        _error(exc)


@router.post("/signoff", status_code=201)
def review(slug: str, payload: ReviewReceipt) -> dict:
    try:
        return signoff(slug, payload.fingerprint, payload.note, payload.acknowledged)
    except (ValueError, OSError, FileNotFoundError, TypeError) as exc:
        _error(exc)
