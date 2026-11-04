"""Whole-manuscript editorial review and explicitly approved batch corrections."""
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .editorial_board import apply, freshness, history, markdown, preview, report, scan

router = APIRouter(prefix="/api/projects/{slug}/editorial-board", tags=["Editorial Board"])


class ScanOptions(BaseModel):
    perspective: str = Field(default="unspecified", pattern="^(unspecified|first|third)$")
    tense: str = Field(default="unspecified", pattern="^(unspecified|past|present)$")


class CorrectionRequest(ScanOptions):
    path: str = Field(min_length=1, max_length=500)
    ids: list[str] = Field(min_length=1, max_length=100)
    source_hash: str = Field(min_length=64, max_length=64)


class Approval(CorrectionRequest):
    proposed_hash: str = Field(min_length=64, max_length=64)


def _fail(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(409, str(exc)) from exc


@router.get("/freshness")
def check_freshness(slug: str):
    try:
        return freshness(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.get("/history")
def scans(slug: str):
    try:
        return history(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/scan")
def run_scan(slug: str, payload: ScanOptions):
    try:
        return scan(slug, payload.perspective, payload.tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/report")
def current(slug: str, payload: ScanOptions):
    try:
        return report(slug, payload.perspective, payload.tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/preview")
def plan_corrections(slug: str, payload: CorrectionRequest):
    try:
        return preview(slug, payload.path, payload.ids, payload.source_hash,
                       payload.perspective, payload.tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.post("/apply")
def apply_corrections(slug: str, payload: Approval):
    try:
        return apply(slug, payload.path, payload.ids, payload.source_hash,
                     payload.proposed_hash, payload.perspective, payload.tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)


@router.get("/report.md", response_class=PlainTextResponse)
def export_report(slug: str, perspective: Literal['unspecified', 'first', 'third'] = 'unspecified',
                  tense: Literal['unspecified', 'past', 'present'] = 'unspecified'):
    try:
        return markdown(slug, perspective, tense)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _fail(exc)
