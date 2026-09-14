from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .provenance import provenance_summary
from .provenance_export import export_provenance
from .voice_audit import analyze_voice

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/provenance")
def summary(slug: str) -> dict:
    try:
        return provenance_summary(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/voice-audit")
def voice_audit(slug: str, path: str | None = Query(default=None)) -> dict:
    try:
        return analyze_voice(slug, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or document not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/provenance/export")
def export(slug: str) -> dict:
    try:
        return export_provenance(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
