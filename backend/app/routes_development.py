from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .development import (
    build_development_context,
    load_development_state,
    save_development_state,
    validate_generated_state,
)
from .development_models import DevelopmentState
from .generation import generate
from .memory import build_memory_context
from .models import ProviderConfig
from .storage import compile_context

router = APIRouter(prefix="/api")

DevelopmentArea = Literal["all", "beats", "character_arcs", "relationships", "threads"]


class DevelopmentGenerateRequest(BaseModel):
    area: DevelopmentArea = "all"
    instruction: str = Field(default="", max_length=12000)
    provider: ProviderConfig
    replace_area: bool = False


class DevelopmentGenerateResponse(BaseModel):
    state: DevelopmentState
    area: DevelopmentArea
    context_files: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """You are EmberWriter's Story Development Editor.
Return ONLY valid JSON. Build practical planning data for a working novelist from the supplied manuscript context, Story Memory, and author-owned development state.

Rules:
- Do not present invented material as established canon. Suggestions must be clearly worded as proposed/planned material.
- Preserve author-owned decisions unless the author explicitly asks to replace them.
- Track causality, character change, setup/payoff, promises, mysteries, threats, relationship movement, and knowledge boundaries.
- Plot beats should each change pressure, knowledge, goal state, relationship state, or stakes.
- Character arcs should distinguish external want from internal need and identify meaningful choices rather than generic personality labels.
- Relationships are stateful and can be complicated. Track trust, closeness, conflict, boundaries, milestones, and unresolved tension without flattening them into a single label.
- Story threads should make setup and intended/observed payoff explicit and identify unresolved promises before the manuscript forgets them.
- Use chapter numbers only when supported by context or explicitly proposed by the author.
- Keep IDs stable when editing existing entries. For new entries, ID may be an empty string; EmberWriter will assign one.

Return an object using these keys when relevant:
{
  "beats": [{"id":"", "title":"", "act":"", "chapter":0, "scene":0, "status":"planned", "pov":"", "summary":"", "purpose":"", "characters":[], "thread_ids":[], "source_path":"", "notes":""}],
  "character_arcs": [{"character":"", "want":"", "need":"", "wound":"", "lie":"", "starting_state":"", "midpoint_shift":"", "climax_choice":"", "ending_state":"", "beat_ids":[], "notes":""}],
  "relationships": [{"id":"", "participants":["A","B"], "label":"", "status":"", "trust":0, "closeness":0, "conflict":0, "chapter":0, "boundaries":[], "milestones":[], "unresolved_tension":[], "notes":""}],
  "threads": [{"id":"", "title":"", "kind":"other", "status":"open", "introduced_chapter":0, "target_payoff_chapter":0, "setup":"", "payoff":"", "participants":[], "beat_ids":[], "source_paths":[], "notes":""}]
}
"""


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Story Development AI did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Story Development AI returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Story Development AI returned an invalid payload")
    return payload


def _merge_area(current: DevelopmentState, generated: dict[str, Any], area: DevelopmentArea) -> DevelopmentState:
    base = current.model_dump()
    keys = ("beats", "character_arcs", "relationships", "threads") if area == "all" else (area,)
    for key in keys:
        if key in generated and isinstance(generated[key], list):
            base[key] = generated[key]
    return validate_generated_state(base)


@router.get("/projects/{slug}/development", response_model=DevelopmentState)
def development_state(slug: str) -> DevelopmentState:
    try:
        return load_development_state(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{slug}/development", response_model=DevelopmentState)
def update_development_state(slug: str, payload: DevelopmentState) -> DevelopmentState:
    try:
        return save_development_state(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/development/generate",
    response_model=DevelopmentGenerateResponse,
)
async def generate_development(slug: str, payload: DevelopmentGenerateRequest) -> DevelopmentGenerateResponse:
    try:
        current = load_development_state(slug)
        author_context = build_development_context(slug, max_items=160)
        query = payload.instruction.strip() or f"Develop the story {payload.area.replace('_', ' ')}"
        manuscript_context, context_files = compile_context(slug, prompt=query)
        memory_context = build_memory_context(slug, query=query, limit=180)
        area_instruction = (
            "Return all four arrays and build a coherent development map across the book."
            if payload.area == "all"
            else f"Focus only on the '{payload.area}' array. Do not return unrelated arrays."
        )
        user_message = f"""REQUESTED AREA
{payload.area}
{area_instruction}

AUTHOR INSTRUCTION
{payload.instruction or 'Build a strong, manuscript-grounded first pass. Preserve established facts and expose gaps.'}

CURRENT AUTHOR-OWNED DEVELOPMENT STATE
{author_context or '(No structured development map exists yet.)'}

STORY MEMORY
{memory_context or '(No structured Story Memory is available yet.)'}

RELEVANT MANUSCRIPT / PROJECT CONTEXT
{manuscript_context or '(No additional manuscript context was retrieved.)'}
"""
        raw = await generate(
            payload.provider,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.28,
            top_p=0.9,
            json_mode=True,
        )
        generated = _parse_json_object(raw)
        if payload.replace_area:
            next_state = _merge_area(current, generated, payload.area)
        else:
            # The model receives current state and is asked to preserve it; merging by area keeps
            # unrelated author-owned structures untouched while allowing the requested area to evolve.
            next_state = _merge_area(current, generated, payload.area)
        saved = save_development_state(slug, next_state)
        files = list(dict.fromkeys(["planning/story-development.json", *context_files]))
        return DevelopmentGenerateResponse(state=saved, area=payload.area, context_files=files)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
