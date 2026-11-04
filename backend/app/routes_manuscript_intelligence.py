"""Read-only whole-novel insights and author-managed story promise ledger."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from .manuscript_intelligence import analyze, create_promise, list_promises, update_promise

router = APIRouter(prefix="/api/projects/{slug}/manuscript-intelligence", tags=["Manuscript Intelligence"])


class PromiseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    tracking_phrase: str = Field(min_length=3, max_length=150)
    intention: str = Field(default="", max_length=1000)


class PromiseDecision(BaseModel):
    status: str = Field(pattern="^(open|resolved|abandoned)$")
    resolution_note: str = Field(default="", max_length=1500)


def _raise(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("/analyze")
def report(slug: str, subjects: list[str] = Query(default=[])) -> dict:
    try:
        return analyze(slug, subjects)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _raise(exc)


@router.get("/promises")
def promises(slug: str) -> list[dict]:
    try:
        return list_promises(slug)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _raise(exc)


@router.post("/promises", status_code=201)
def add_promise(slug: str, payload: PromiseCreate) -> dict:
    try:
        return create_promise(slug, **payload.model_dump())
    except (FileNotFoundError, ValueError, OSError) as exc:
        _raise(exc)


@router.patch("/promises/{promise_id}")
def decide_promise(slug: str, promise_id: str, payload: PromiseDecision) -> dict:
    try:
        return update_promise(slug, promise_id, payload.status, payload.resolution_note)
    except (FileNotFoundError, ValueError, OSError) as exc:
        _raise(exc)
