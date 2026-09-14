from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .character_voice import (
    CharacterVoiceCard,
    CharacterVoiceState,
    delete_character_voice,
    infer_character_voice,
    load_character_voices,
    upsert_character_voice,
)
from .memory_integrity import reconcile_story_memory
from .models import ProviderConfig, ScenePlanRequest, ScenePlanResponse, StoryIntelligenceResponse
from .scene_architect import create_scene_plan
from .story_intelligence import build_story_intelligence

router = APIRouter(prefix="/api")


class CharacterVoiceInferRequest(BaseModel):
    provider: ProviderConfig
    author_notes: str = Field(default="", max_length=8000)


@router.get("/projects/{slug}/story-intelligence", response_model=StoryIntelligenceResponse)
def story_intelligence(slug: str) -> dict:
    try:
        reconcile_story_memory(slug)
        return build_story_intelligence(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/projects/{slug}/character-voices", response_model=CharacterVoiceState)
def character_voices(slug: str) -> CharacterVoiceState:
    try:
        return load_character_voices(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.put("/projects/{slug}/character-voices/{character}", response_model=CharacterVoiceState)
def save_character_voice(slug: str, character: str, payload: CharacterVoiceCard) -> CharacterVoiceState:
    try:
        card = payload.model_copy(update={"character": character})
        return upsert_character_voice(slug, card)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{slug}/character-voices/{character}", response_model=CharacterVoiceState)
def remove_character_voice(slug: str, character: str) -> CharacterVoiceState:
    try:
        return delete_character_voice(slug, character)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/character-voices/{character}/infer", response_model=CharacterVoiceCard)
async def infer_voice(slug: str, character: str, payload: CharacterVoiceInferRequest) -> CharacterVoiceCard:
    try:
        reconcile_story_memory(slug)
        return await infer_character_voice(
            slug,
            character=character,
            provider=payload.provider,
            author_notes=payload.author_notes,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/{slug}/scene-plan", response_model=ScenePlanResponse)
async def scene_plan(slug: str, payload: ScenePlanRequest) -> dict:
    try:
        reconcile_story_memory(slug)
        return await create_scene_plan(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or active manuscript file not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
