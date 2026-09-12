from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .previewing import build_preview_site, preview_payload

router = APIRouter(prefix="/api/projects/{slug}/preview")


class PreviewRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    author: str = Field(default="", max_length=240)
    trim_width: float = Field(default=6.0, ge=4.0, le=8.5)
    trim_height: float = Field(default=9.0, ge=6.0, le=11.7)


@router.post("")
def preview(slug: str, payload: PreviewRequest) -> dict:
    try:
        return preview_payload(slug, **payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/site")
def preview_site(slug: str, payload: PreviewRequest) -> dict:
    try:
        return build_preview_site(slug, title=payload.title, author=payload.author)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
