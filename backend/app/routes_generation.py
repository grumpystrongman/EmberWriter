from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from .generation import build_messages, generate, list_models
from .memory import build_memory_context
from .models import (
    ContextRequest,
    ContextResponse,
    GenerateRequest,
    GenerateResponse,
    ProviderConfig,
)
from .storage import compile_context

router = APIRouter(prefix="/api")


def _with_narrative_memory(
    slug: str,
    context_text: str,
    context_files: list[str],
    prompt: str,
    selected_text: str | None,
) -> tuple[str, list[str]]:
    query = " ".join(part for part in (prompt, selected_text or "") if part).strip()
    memory_text = build_memory_context(slug, query=query, limit=30)
    if not memory_text:
        return context_text, context_files
    enriched = f"{memory_text}\n\n---\n\n{context_text}" if context_text else memory_text
    files = ["summaries/narrative-memory.json", *context_files]
    return enriched, list(dict.fromkeys(files))


@router.post("/models")
async def models(payload: ProviderConfig) -> dict:
    try:
        return {"models": await list_models(payload)}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach model server: {exc}") from exc


@router.post("/projects/{slug}/context", response_model=ContextResponse)
def context(slug: str, payload: ContextRequest) -> ContextResponse:
    try:
        compiled, files = compile_context(
            slug,
            prompt=payload.prompt,
            active_file=payload.active_file,
            selected_text=payload.selected_text,
        )
        compiled, files = _with_narrative_memory(
            slug,
            compiled,
            files,
            payload.prompt,
            payload.selected_text,
        )
        return ContextResponse(context=compiled, files=files)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/generate", response_model=GenerateResponse)
async def generate_text(slug: str, payload: GenerateRequest) -> GenerateResponse:
    try:
        context_text, context_files = compile_context(
            slug,
            prompt=payload.prompt,
            active_file=payload.active_file,
            selected_text=payload.selected_text,
        )
        context_text, context_files = _with_narrative_memory(
            slug,
            context_text,
            context_files,
            payload.prompt,
            payload.selected_text,
        )
        messages = build_messages(payload.mode, payload.prompt, context_text)
        text = await generate(payload.provider, messages)
        return GenerateResponse(text=text, context_files=context_files)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
