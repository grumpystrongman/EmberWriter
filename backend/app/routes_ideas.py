from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .ideas import add_idea, delete_idea, list_ideas, update_idea

router = APIRouter(prefix="/api/projects/{slug}/ideas")


class IdeaCreate(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    kind: Literal["idea", "dialogue", "character", "world", "plot", "scene", "research", "todo"] = "idea"
    source: Literal["typed", "speech"] = "typed"
    destination: str = Field(default="inbox", max_length=120)
    context_path: str = Field(default="", max_length=500)


class IdeaPatch(BaseModel):
    text: str | None = Field(default=None, max_length=20000)
    kind: str | None = Field(default=None, max_length=80)
    destination: str | None = Field(default=None, max_length=120)
    context_path: str | None = Field(default=None, max_length=500)
    status: Literal["open", "routed", "archived"] | None = None


@router.get("")
def ideas(slug: str) -> list[dict]:
    try:
        return list_ideas(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("")
def create_idea(slug: str, payload: IdeaCreate) -> dict:
    try:
        return add_idea(
            slug,
            payload.text,
            kind=payload.kind,
            source=payload.source,
            destination=payload.destination,
            context_path=payload.context_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{idea_id}")
def patch_idea(slug: str, idea_id: str, payload: IdeaPatch) -> dict:
    try:
        return update_idea(slug, idea_id, payload.model_dump(exclude_unset=True))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{idea_id}", status_code=204)
def remove_idea(slug: str, idea_id: str) -> None:
    try:
        delete_idea(slug, idea_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc
