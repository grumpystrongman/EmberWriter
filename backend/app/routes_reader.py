from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query

from .reader_models import (
    ReaderPersonaDefinition,
    ReaderRun,
    ReaderRunCreate,
    ReaderRunSummary,
    ReaderStepRequest,
    ReaderStepResponse,
)
from .readers import create_reader_run, get_reader_run, list_reader_runs, persona_catalog, step_reader_run
from .storage import get_project

router = APIRouter(prefix="/api/projects/{slug}/readers")


def _require_project(slug: str) -> None:
    get_project(slug)


@router.get("/personas", response_model=list[ReaderPersonaDefinition])
def personas(slug: str) -> list[dict]:
    try:
        _require_project(slug)
        return persona_catalog()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/runs", response_model=ReaderRun)
def create_run(slug: str, payload: ReaderRunCreate) -> dict:
    try:
        _require_project(slug)
        return create_reader_run(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=list[ReaderRunSummary])
def runs(slug: str, limit: Annotated[int, Query(ge=1, le=100)] = 30) -> list[dict]:
    try:
        _require_project(slug)
        return list_reader_runs(slug, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/runs/{run_id}", response_model=ReaderRun)
def run(slug: str, run_id: str) -> dict:
    try:
        _require_project(slug)
        return get_reader_run(slug, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Reader run not found") from exc


@router.post("/runs/{run_id}/step", response_model=ReaderStepResponse)
async def step(slug: str, run_id: str, payload: ReaderStepRequest) -> dict:
    try:
        _require_project(slug)
        return await step_reader_run(slug, run_id, payload.provider)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Reader run or source document not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
