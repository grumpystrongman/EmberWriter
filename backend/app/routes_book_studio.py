"""Local-only whole-book drafting endpoints with explicit review."""
import asyncio
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .book_studio import approve, candidate, configure, decline, draft_next, load_state, revise_chapter_brief, edit_candidate, suggest_outline
from .models import ProviderConfig

router = APIRouter(prefix="/api/projects/{slug}/book-studio", tags=["Book Studio"])


class ChapterBrief(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    brief: str = Field(min_length=1, max_length=3000)


class BookPlan(BaseModel):
    premise: str = Field(min_length=1, max_length=8000)
    voice: str = Field(default="", max_length=3000)
    chapters: list[ChapterBrief] = Field(min_length=1, max_length=80)
    target_words: int = Field(default=1500, ge=300, le=5000)


class DraftRequest(BaseModel):
    provider: ProviderConfig


@router.get("")
def plan(slug: str) -> dict:
    try:
        return load_state(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("")
def update_plan(slug: str, payload: BookPlan) -> dict:
    try:
        return configure(slug, **payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


class OutlineRequest(BaseModel):
    premise: str = Field(min_length=1, max_length=8000)
    voice: str = Field(default="", max_length=3000)
    chapter_count: int = Field(default=12, ge=1, le=80)
    provider: ProviderConfig


@router.post("/suggest-outline")
async def propose_outline(slug: str, payload: OutlineRequest) -> dict:
    try:
        chapters = await suggest_outline(slug, premise=payload.premise, voice=payload.voice,
                                         chapter_count=payload.chapter_count, config=payload.provider)
        return {"chapters": chapters, "saved": False, "author_review_required": True}
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except (httpx.HTTPError, RuntimeError, asyncio.TimeoutError) as exc:
        raise HTTPException(502, str(exc)[:500]) from exc


@router.put("/chapters/{number}")
def edit_brief(slug: str, number: int, payload: ChapterBrief) -> dict:
    try:
        return revise_chapter_brief(slug, number, payload.title, payload.brief)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/draft-next")
async def draft(slug: str, payload: DraftRequest) -> dict:
    try:
        return await draft_next(slug, payload.provider)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except (httpx.HTTPError, RuntimeError, asyncio.TimeoutError) as exc:
        raise HTTPException(502, str(exc)[:500]) from exc


@router.get("/candidates/{number}")
def get_candidate(slug: str, number: int) -> dict:
    try:
        return candidate(slug, number)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


class CandidateEdit(BaseModel):
    content: str = Field(min_length=1, max_length=1_000_000)


@router.put("/candidates/{number}")
def update_candidate(slug: str, number: int, payload: CandidateEdit) -> dict:
    try:
        return edit_candidate(slug, number, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/candidates/{number}/approve")
def approve_candidate(slug: str, number: int) -> dict:
    try:
        return approve(slug, number)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/candidates/{number}/decline")
def decline_candidate(slug: str, number: int) -> dict:
    try:
        return decline(slug, number)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
