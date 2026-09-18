from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .character_voice import build_character_voice_context
from .chemistry import build_chemistry_context
from .craft import build_craft_context, quality_pass
from .development import DEVELOPMENT_PATH, build_development_context
from .generation import (
    PROSE_MODES,
    build_messages,
    generate,
    generate_complete_prose,
    list_models,
    scene_word_floor,
)
from .generation_guard import (
    generation_timeout_seconds,
    register_generation_task,
    unregister_generation_task,
)
from .memory import build_memory_context
from .memory_integrity import reconcile_story_memory
from .models import (
    ContextRequest,
    ContextResponse,
    GenerateRequest,
    GenerateResponse,
    ProviderConfig,
)
from .prose_quality import quality_guidance
from .provenance_store import record_assistance_event
from .storage import compile_context, read_text
from .story_intelligence import build_character_context, relevant_character_names
from .streaming_generation import generate_complete_prose_streamed, generate_streamed
from .studio_context import STUDIO_CONTEXT_SENTINEL, build_studio_context

router = APIRouter(prefix="/api")

_GENERATION_CONTEXT_MAX_CHARS = 76000
_CONTEXT_SEPARATOR = "\n\n---\n\n"
_ACTIVE_ANCHOR_MARKER = "## HIGH-PRIORITY ACTIVE CONTINUATION ANCHOR"

_STUDIO_HANDOFF_MARKER = "EXISTING DRAFT HANDOFF — REFERENCE ONLY; DO NOT REPEAT"
_STUDIO_HANDOFF_END_MARKER = "WRITE ONLY NEW PROSE THAT COMES AFTER THAT FINAL LINE."


def _studio_continuation_existing_words(prompt: str) -> int:
    if _STUDIO_HANDOFF_MARKER not in prompt:
        return 0
    handoff = prompt.split(_STUDIO_HANDOFF_MARKER, 1)[1]
    if _STUDIO_HANDOFF_END_MARKER in handoff:
        handoff = handoff.split(_STUDIO_HANDOFF_END_MARKER, 1)[0]
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", handoff))



def _relevant_names(slug: str, context_text: str, prompt: str, selected_text: str | None) -> list[str]:
    probe = f"{prompt}\n{selected_text or ''}\n{context_text[-18000:]}"
    return relevant_character_names(slug, probe)


def _with_active_tail(
    slug: str,
    context_text: str,
    context_files: list[str],
    active_file: str | None,
) -> tuple[str, list[str]]:
    """Prepend the newest manuscript text as the authoritative continuation anchor.

    compile_context historically excerpts files from the beginning. For a long chapter that
    means `continue` can see the opening fight more strongly than the current scene at EOF.
    Keep broad context for continuity, but put the latest 18k characters ahead of it.
    """
    if not active_file:
        return context_text, context_files
    try:
        active = read_text(slug, active_file)
    except (FileNotFoundError, ValueError, OSError):
        return context_text, context_files
    tail = active[-18000:].strip()
    if not tail:
        return context_text, context_files
    anchor = (
        f"{_ACTIVE_ANCHOR_MARKER}\n"
        f"Source: {active_file}\n"
        "This is the latest text in the active manuscript. Continue from its END, not from older retrieved passages.\n\n"
        f"{tail}"
    )
    enriched = f"{anchor}{_CONTEXT_SEPARATOR}{context_text}" if context_text else anchor
    return enriched, list(dict.fromkeys([active_file, *context_files]))


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
    enriched = f"{memory_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else memory_text
    files = ["summaries/narrative-memory.json", *context_files]
    return enriched, list(dict.fromkeys(files))


def _with_development_map(
    slug: str,
    context_text: str,
    context_files: list[str],
) -> tuple[str, list[str]]:
    development_text = build_development_context(slug, max_items=100)
    if not development_text:
        return context_text, context_files
    enriched = f"{development_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else development_text
    return enriched, list(dict.fromkeys([DEVELOPMENT_PATH, *context_files]))


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
    enriched = f"{character_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else character_text
    return enriched, context_files


def _with_character_voices(
    slug: str,
    context_text: str,
    context_files: list[str],
    prompt: str,
    selected_text: str | None,
) -> tuple[str, list[str]]:
    names = _relevant_names(slug, context_text, prompt, selected_text)
    voice_text, voice_files = build_character_voice_context(slug, names)
    if not voice_text:
        return context_text, context_files
    enriched = f"{voice_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else voice_text
    return enriched, list(dict.fromkeys([*voice_files, *context_files]))


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
    enriched = f"{chemistry_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else chemistry_text
    return enriched, list(dict.fromkeys([*chemistry_files, *context_files]))


def _with_craft_context(
    slug: str,
    context_text: str,
    context_files: list[str],
    payload: GenerateRequest,
) -> tuple[str, list[str], str]:
    craft_text, craft_files = build_craft_context(slug, payload.craft)
    enriched = f"{craft_text}{_CONTEXT_SEPARATOR}{context_text}" if context_text else craft_text
    files = [*craft_files, *context_files]
    return enriched, list(dict.fromkeys(files)), craft_text


def _cap_generation_context(context_text: str, max_chars: int = _GENERATION_CONTEXT_MAX_CHARS) -> str:
    """Keep local-model prompt evaluation bounded without dropping the active continuation tail.

    The context enrichers intentionally prepend high-value craft/character state. Long projects can
    otherwise grow well beyond a local model's practical context window before output tokens are even
    considered. Preserve the newest manuscript anchor explicitly, then retain high-priority head context
    and a slice of the broad story context from the end.
    """
    if len(context_text) <= max_chars:
        return context_text

    marker_index = context_text.find(_ACTIVE_ANCHOR_MARKER)
    anchor = ""
    remainder = context_text
    if marker_index >= 0:
        anchor_end = context_text.find(_CONTEXT_SEPARATOR, marker_index)
        if anchor_end < 0:
            anchor_end = min(len(context_text), marker_index + 18000)
            suffix_start = anchor_end
        else:
            suffix_start = anchor_end + len(_CONTEXT_SEPARATOR)
        anchor = context_text[marker_index:anchor_end].strip()
        remainder = f"{context_text[:marker_index]}{context_text[suffix_start:]}".strip()

    separator_cost = len(_CONTEXT_SEPARATOR) * (2 if anchor else 1)
    remaining = max(0, max_chars - len(anchor) - separator_cost)
    head_budget = int(remaining * 0.66)
    tail_budget = max(0, remaining - head_budget)
    head = remainder[:head_budget].rstrip()
    tail = remainder[-tail_budget:].lstrip() if tail_budget else ""
    pieces = [piece for piece in (head, anchor, tail) if piece]
    capped = _CONTEXT_SEPARATOR.join(pieces)
    return capped[:max_chars]


def _is_studio_request(payload: GenerateRequest) -> bool:
    return payload.selected_text == STUDIO_CONTEXT_SENTINEL


def _prepare_generation_context(slug: str, payload: GenerateRequest) -> tuple[str, list[str], str]:
    if _is_studio_request(payload):
        context_text, context_files, craft_text, _ = build_studio_context(
            slug,
            payload.prompt,
            payload.craft,
        )
        return _cap_generation_context(context_text, max_chars=36000), context_files, craft_text

    reconcile_story_memory(slug)
    context_text, context_files = compile_context(
        slug,
        prompt=payload.prompt,
        active_file=payload.active_file,
        selected_text=payload.selected_text,
    )
    context_text, context_files = _with_active_tail(slug, context_text, context_files, payload.active_file)
    context_text, context_files = _with_narrative_memory(
        slug,
        context_text,
        context_files,
        payload.prompt,
        payload.selected_text,
    )
    context_text, context_files = _with_development_map(slug, context_text, context_files)
    context_text, context_files = _with_character_intelligence(
        slug,
        context_text,
        context_files,
        payload.prompt,
        payload.selected_text,
    )
    context_text, context_files = _with_character_voices(
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
    return _cap_generation_context(context_text), context_files, craft_text


def _selected_text_for_record(payload: GenerateRequest) -> str | None:
    return None if _is_studio_request(payload) else payload.selected_text


@router.post("/models")
async def models(payload: ProviderConfig) -> dict:
    try:
        return {"models": await list_models(payload)}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach model server: {exc}") from exc


@router.post("/projects/{slug}/context", response_model=ContextResponse)
def context(slug: str, payload: ContextRequest) -> ContextResponse:
    try:
        reconcile_story_memory(slug)
        compiled, files = compile_context(
            slug,
            prompt=payload.prompt,
            active_file=payload.active_file,
            selected_text=payload.selected_text,
        )
        compiled, files = _with_active_tail(slug, compiled, files, payload.active_file)
        compiled, files = _with_narrative_memory(
            slug,
            compiled,
            files,
            payload.prompt,
            payload.selected_text,
        )
        compiled, files = _with_development_map(slug, compiled, files)
        compiled, files = _with_character_intelligence(
            slug,
            compiled,
            files,
            payload.prompt,
            payload.selected_text,
        )
        compiled, files = _with_character_voices(
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


async def _generate_payload(
    slug: str,
    payload: GenerateRequest,
    *,
    streamed: bool = False,
    on_delta=None,
    on_status=None,
) -> GenerateResponse:
    context_text, context_files, craft_text = _prepare_generation_context(slug, payload)
    heat = payload.craft.heat_level
    minimum_words = scene_word_floor(payload.prompt, heat)
    if _is_studio_request(payload) and payload.mode == "continue":
        existing_words = _studio_continuation_existing_words(payload.prompt)
        if existing_words:
            # The Working Draft already counts toward scene length. A continuation should finish
            # the scene, not manufacture another Inferno-sized block of hesitation/padding.
            minimum_words = max(220, minimum_words - existing_words)
    messages = build_messages(
        payload.mode,
        payload.prompt,
        context_text,
        heat_level=heat,
        finish_scene=payload.mode in PROSE_MODES,
        min_scene_words=minimum_words,
    )

    if streamed:
        if on_delta is None:
            raise ValueError("Streaming generation requires an output callback")
        if payload.mode in PROSE_MODES:
            text = await generate_complete_prose_streamed(
                payload.provider,
                messages,
                min_words=minimum_words,
                on_delta=on_delta,
                on_status=on_status,
            )
        else:
            if on_status is not None:
                await on_status("Generating…")
            text = (
                await generate_streamed(
                    payload.provider,
                    messages,
                    on_delta=on_delta,
                )
            ).strip()
    elif payload.mode in PROSE_MODES:
        text = await generate_complete_prose(
            payload.provider,
            messages,
            min_words=minimum_words,
        )
    else:
        text = await generate(payload.provider, messages)

    refined = False
    if payload.craft.quality_pass and payload.mode in PROSE_MODES:
        if on_status is not None:
            await on_status("Applying Craft Pass…")
        targets = quality_guidance(text)
        text = await quality_pass(
            payload.provider,
            draft=text,
            author_prompt=(
                f"{payload.prompt}\n\nDETERMINISTIC PROSE-QUALITY TARGETS\n{targets}\n\n"
                "Repair only issues that are genuinely present. Preserve intentional repetition, roughness, rhythm, character-specific language, and the complete scene."
            ),
            craft_context=craft_text,
        )
        refined = True

    event = record_assistance_event(
        slug,
        mode=payload.mode,
        active_file=payload.active_file,
        prompt=payload.prompt,
        selected_text=_selected_text_for_record(payload),
        output_text=text,
        context_files=context_files,
        refined=refined,
        provider=payload.provider.provider,
        model=payload.provider.model,
    )
    return GenerateResponse(
        text=text,
        context_files=context_files,
        refined=refined,
        assistance_event_id=event["id"],
    )


@router.post("/projects/{slug}/generate", response_model=GenerateResponse)
async def generate_text(slug: str, payload: GenerateRequest) -> GenerateResponse:
    try:
        return await _generate_payload(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _produce_generation_stream(
    slug: str,
    payload: GenerateRequest,
    queue: asyncio.Queue[dict[str, object] | None],
) -> None:
    streamed_parts: list[str] = []
    context_files: list[str] = []

    async def emit_delta(text: str) -> None:
        if not text:
            return
        streamed_parts.append(text)
        await queue.put({"type": "delta", "text": text})

    async def emit_status(message: str) -> None:
        if message.startswith(("Hard-canon conflict detected", "Non-manuscript assistant response detected ·")):
            streamed_parts.clear()
            await queue.put({"type": "reset", "reason": message})
        await queue.put({"type": "status", "message": message})

    async def partial_or_error(detail: str) -> None:
        partial = "".join(streamed_parts).strip()
        if partial:
            await queue.put(
                {
                    "type": "final",
                    "text": partial,
                    "context_files": context_files,
                    "refined": False,
                    "assistance_event_id": None,
                    "partial": True,
                    "warning": detail,
                }
            )
        else:
            await queue.put({"type": "error", "detail": detail})

    try:
        await emit_status(
            "Preparing Studio context…" if _is_studio_request(payload) else "Preparing story context…"
        )
        async with asyncio.timeout(generation_timeout_seconds()):
            # Prepare context separately so partial-result errors can still report which source
            # files were involved after model generation has started.
            context_text, context_files, craft_text = _prepare_generation_context(slug, payload)
            heat = payload.craft.heat_level
            minimum_words = scene_word_floor(payload.prompt, heat)
            messages = build_messages(
                payload.mode,
                payload.prompt,
                context_text,
                heat_level=heat,
                finish_scene=payload.mode in PROSE_MODES,
                min_scene_words=minimum_words,
            )

            if payload.mode in PROSE_MODES:
                text = await generate_complete_prose_streamed(
                    payload.provider,
                    messages,
                    min_words=minimum_words,
                    on_delta=emit_delta,
                    on_status=emit_status,
                )
            else:
                await emit_status("Generating…")
                text = (
                    await generate_streamed(
                        payload.provider,
                        messages,
                        on_delta=emit_delta,
                    )
                ).strip()

            refined = False
            if payload.craft.quality_pass and payload.mode in PROSE_MODES:
                await emit_status("Applying Craft Pass…")
                targets = quality_guidance(text)
                text = await quality_pass(
                    payload.provider,
                    draft=text,
                    author_prompt=(
                        f"{payload.prompt}\n\nDETERMINISTIC PROSE-QUALITY TARGETS\n{targets}\n\n"
                        "Repair only issues that are genuinely present. Preserve intentional repetition, roughness, rhythm, character-specific language, and the complete scene."
                    ),
                    craft_context=craft_text,
                )
                refined = True

            event = record_assistance_event(
                slug,
                mode=payload.mode,
                active_file=payload.active_file,
                prompt=payload.prompt,
                selected_text=_selected_text_for_record(payload),
                output_text=text,
                context_files=context_files,
                refined=refined,
                provider=payload.provider.provider,
                model=payload.provider.model,
            )
            await queue.put(
                {
                    "type": "final",
                    "text": text,
                    "context_files": context_files,
                    "refined": refined,
                    "assistance_event_id": event["id"],
                    "partial": False,
                }
            )
    except TimeoutError:
        await partial_or_error(
            "Generation reached EmberWriter's total time limit. Any prose already produced has been preserved as a partial result."
        )
    except asyncio.CancelledError:
        raise
    except FileNotFoundError:
        await partial_or_error("Project not found")
    except (TypeError, ValueError) as exc:
        await partial_or_error(str(exc))
    except httpx.HTTPError as exc:
        await partial_or_error(f"Model server error: {exc}")
    except RuntimeError as exc:
        await partial_or_error(str(exc))
    except Exception as exc:  # pragma: no cover - final defensive boundary for streamed responses
        await partial_or_error(f"Generation failed: {type(exc).__name__}: {exc}")
    finally:
        queue.put_nowait(None)


@router.post("/projects/{slug}/generate/stream")
async def generate_text_stream(slug: str, payload: GenerateRequest) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()
    task = asyncio.create_task(
        _produce_generation_stream(slug, payload, queue),
        name=f"ember-stream-generation:{slug}",
    )
    if not register_generation_task(slug, task):
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        raise HTTPException(
            status_code=409,
            detail="A generation is already running for this project. Cancel it before starting another.",
        )

    async def events():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            unregister_generation_task(slug, task)

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
