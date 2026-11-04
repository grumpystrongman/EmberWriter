"""Author-controlled, local-only Autopilot foundation endpoints."""
from fastapi import APIRouter, HTTPException

from .autopilot import audit_history, current_readiness, run_audit

router = APIRouter(prefix="/api/projects/{slug}/autopilot", tags=["Autopilot"])


@router.get("/readiness")
def readiness(slug: str) -> dict:
    try:
        return current_readiness(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/audits")
def audits(slug: str) -> list[dict]:
    try:
        return audit_history(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/audits")
def create_audit(slug: str) -> dict:
    try:
        return run_audit(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
