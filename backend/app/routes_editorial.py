from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from .editorial import (
    get_editorial_profile,
    get_editorial_run,
    list_editorial_findings,
    list_editorial_runs,
    report_catalog,
    run_editorial,
    save_editorial_profile,
    update_finding_status,
)
from .editorial_models import (
    EditorialFinding,
    EditorialFindingStatusUpdate,
    EditorialProfile,
    EditorialReportDefinition,
    EditorialRunRequest,
    EditorialRunResult,
    EditorialRunSummary,
)
from .storage import get_project

router = APIRouter(prefix="/api/projects/{slug}/editorial")


def _require_project(slug: str) -> None:
    get_project(slug)


@router.get("/reports", response_model=list[EditorialReportDefinition])
def reports(slug: str) -> list[dict]:
    try:
        _require_project(slug)
        return report_catalog()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/profile", response_model=EditorialProfile)
def profile(slug: str) -> EditorialProfile:
    try:
        _require_project(slug)
        return get_editorial_profile(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.put("/profile", response_model=EditorialProfile)
def update_profile(slug: str, payload: EditorialProfile) -> EditorialProfile:
    try:
        _require_project(slug)
        return save_editorial_profile(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs", response_model=EditorialRunResult)
def create_run(slug: str, payload: EditorialRunRequest) -> dict:
    try:
        _require_project(slug)
        return run_editorial(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or document not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=list[EditorialRunSummary])
def runs(slug: str, limit: Annotated[int, Query(ge=1, le=200)] = 30) -> list[dict]:
    try:
        _require_project(slug)
        return list_editorial_runs(slug, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/runs/{run_id}", response_model=EditorialRunResult)
def run(slug: str, run_id: str) -> dict:
    try:
        _require_project(slug)
        return get_editorial_run(slug, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Editorial run not found") from exc


@router.get("/findings", response_model=list[EditorialFinding])
def findings(
    slug: str,
    run_id: str | None = None,
    report_id: str | None = None,
    status: Literal["open", "resolved", "ignored"] | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> list[dict]:
    try:
        _require_project(slug)
        return list_editorial_findings(
            slug,
            run_id=run_id,
            report_id=report_id,
            status=status,
            limit=limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/findings/{finding_id}", response_model=EditorialFinding)
def set_finding_status(slug: str, finding_id: str, payload: EditorialFindingStatusUpdate) -> dict:
    try:
        _require_project(slug)
        return update_finding_status(slug, finding_id, payload.status)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Editorial finding not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
