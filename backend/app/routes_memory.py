from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query

from .memory import analyze_document, list_memory, memory_stats
from .memory_integrity import reconcile_story_memory
from .models import AnalyzeRequest, AnalyzeResponse, MemoryFact, MemoryStats

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/memory", response_model=list[MemoryFact])
def memory(
    slug: str,
    query: str = "",
    kind: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 80,
) -> list[dict]:
    try:
        reconcile_story_memory(slug)
        return list_memory(slug, query=query, kinds=kind, limit=limit)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/projects/{slug}/memory/stats", response_model=MemoryStats)
def stats(slug: str) -> dict:
    try:
        reconcile_story_memory(slug)
        return memory_stats(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/memory/analyze", response_model=AnalyzeResponse)
async def analyze(slug: str, payload: AnalyzeRequest) -> dict:
    try:
        reconcile_story_memory(slug)
        return await analyze_document(
            slug,
            path=payload.path,
            provider=payload.provider,
            force=payload.force,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Manuscript file not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
