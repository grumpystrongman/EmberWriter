"""Project-local author terminology and style rules."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .style_bible import add, audit, decide, delete, rules

router = APIRouter(prefix="/api/projects/{slug}/style-bible", tags=["Style Bible"])


class RuleCreate(BaseModel):
    category: str = Field(pattern="^(preferred|avoid|watch)$")
    phrase: str = Field(min_length=2, max_length=120)
    preferred: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=500)
    case_sensitive: bool = False


class Decision(BaseModel):
    action: str = Field(pattern="^(dismiss|reopen)$")
    reason: str = Field(default="", max_length=500)


def _error(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("/rules")
def all_rules(slug: str) -> list[dict]:
    try:
        return rules(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/rules", status_code=201)
def create_rule(slug: str, payload: RuleCreate) -> dict:
    try:
        return add(slug, **payload.model_dump())
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.delete("/rules/{rule_id}")
def remove_rule(slug: str, rule_id: str) -> dict:
    try:
        return delete(slug, rule_id)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.get("/audit")
def run_audit(slug: str) -> dict:
    try:
        return audit(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)


@router.post("/findings/{finding_id}")
def decide_finding(slug: str, finding_id: str, payload: Decision) -> dict:
    try:
        return decide(slug, finding_id, payload.action, payload.reason)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
