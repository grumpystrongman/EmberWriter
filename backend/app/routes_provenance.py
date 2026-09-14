from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .provenance import provenance_summary
from .provenance_export import export_provenance
from .provenance_store import record_assistance_decision
from .voice_audit import analyze_voice

router = APIRouter(prefix="/api")


class AssistanceDecisionRequest(BaseModel):
    decision: Literal["accepted_append", "accepted_replace", "rejected", "partial", "copied"]
    active_file: str | None = Field(default=None, max_length=500)
    note: str = Field(default="", max_length=1000)


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


@router.post("/projects/{slug}/provenance/assistance/{event_id}/decision")
def assistance_decision(slug: str, event_id: str, payload: AssistanceDecisionRequest) -> dict:
    try:
        return record_assistance_decision(
            slug,
            assistance_event_id=event_id,
            decision=payload.decision,
            active_file=payload.active_file,
            note=payload.note,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Assistance event not found") from exc
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
