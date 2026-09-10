from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from .chemistry import build_chemistry_context
from .craft import build_craft_context, quality_pass
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
from .story_intelligence import build_character_context, relevant_character_names

router = APIRouter(prefix="/api")


def _relevant_names(slug: str, context_text: str, prompt: str, selected_text: str | None) -> list[str]:
    probe = f"{prompt}\n{selected_text or ''}\n{context_text[-18000:]}"
    return relevant_character_names(slug, probe)


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


def _with_character_intelligence(
    slug: str,
    context_text: str,
    context_files: list[str],
    prompt: str,
    selected_text: str | None,
) -> tuple[str, list[str]]:
    names = _relevant_names(slug, context_text, prompt, selected_text)
    if not names:
        return context_text, context_files
    character_text = build_character_context(slug, names)
    if not character_text:
        return context_text, context_files
    enriched = f"{character_text}\n\n---\n\n{context_text}" if context_text else character_text
    return enriched, context_files


def _with_chemistry(
    slug: str,
    context_text: str,
    context_files: list[str],
    prompt: str,
    selected_text: str | None,
) -> tuple[str, list[str]]:
    names = _relevant_names(slug, context_text, prompt, selected_text)
    if len(names) < 2:
        return context_text, context_files
    chemistry_text, chemistry_files = build_chemistry_context(slug, names)
    if not chemistry_text:
        return context_text, context_files
    enriched = f"{chemistry_text}\n\n---\n\n{context_text}" if context_text else chemistry_text
    return enriched, list(dict.fromkeys([*chemistry_files, *context_files]))


def _with_craft_context(
    slug: str,
    context_text: str,
    context_files: list[str],
    payload: GenerateRequest,
) -> tuple[str, list[str], str]:
    craft_text, craft_files = build_craft_context(slug, payload.craft)
    enriched = f"{craft_text}\n\n---\n\n{context_text}" if context_text else craft_text
    files = [*craft_files, *context_files]
    return enriched, list(dict.fromkeys(files)), craft_text


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
        compiled, files = _with_character_intelligence(
            slug,
            compiled,
            files,
            payload.prompt,
            payload.selected_text,
        )
        compiled, files = _with_chemistry(
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
        context_text, context_files = _with_character_intelligence(
            slug,
            context_text,
            context_files,
            payload.prompt,
            payload.selected_text,
        )
        context_text, context_files = _with_chemistry(
            slug,
            context_text,
            context_files,
            payload.prompt,
            payload.selected_text,
        )
        context_text, context_files, craft_text = _with_craft_context(
            slug,
            context_text,
            context_files,
            payload,
        )
        messages = build_messages(payload.mode, payload.prompt, context_text)
        text = await generate(payload.provider, messages)
        refined = False
        if payload.craft.quality_pass and payload.mode in {"write", "continue", "rewrite"}:
            text = await quality_pass(
                payload.provider,
                draft=text,
                author_prompt=payload.prompt,
                craft_context=craft_text,
            )
            refined = True
        return GenerateResponse(text=text, context_files=context_files, refined=refined)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
