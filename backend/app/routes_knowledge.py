from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from .knowledge import (
    answer_knowledge,
    grammar_review,
    index_embeddings,
    list_sources,
    refresh_due_sources,
    search_knowledge,
)
from .knowledge_models import (
    GrammarReviewRequest,
    GrammarReviewResponse,
    KnowledgeAnswerRequest,
    KnowledgeAnswerResponse,
    KnowledgeChunk,
    KnowledgeEmbeddingRequest,
    KnowledgeEmbeddingResponse,
    KnowledgeRefreshRequest,
    KnowledgeRefreshResponse,
    KnowledgeSearchRequest,
    KnowledgeSource,
)

router = APIRouter(prefix="/api/knowledge")


@router.get("/sources", response_model=list[KnowledgeSource])
def sources() -> list[dict]:
    return list_sources()


@router.post("/search", response_model=list[KnowledgeChunk])
async def search(payload: KnowledgeSearchRequest) -> list[dict]:
    try:
        return await search_knowledge(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding server error: {exc}") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/refresh", response_model=KnowledgeRefreshResponse)
async def refresh(payload: KnowledgeRefreshRequest) -> dict:
    try:
        return await refresh_due_sources(payload.source_ids or None)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/embeddings/index", response_model=KnowledgeEmbeddingResponse)
async def embeddings(payload: KnowledgeEmbeddingRequest) -> dict:
    try:
        return await index_embeddings(payload.embedding, payload.categories, payload.force)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding server error: {exc}") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/grammar/review", response_model=GrammarReviewResponse)
async def review_grammar(payload: GrammarReviewRequest) -> dict:
    try:
        return await grammar_review(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/answer", response_model=KnowledgeAnswerResponse)
async def answer(payload: KnowledgeAnswerRequest) -> dict:
    try:
        return await answer_knowledge(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
