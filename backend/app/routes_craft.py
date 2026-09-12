from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .craft import (
    VOICE_PROFILE_PATH,
    analyze_voice,
    get_craft_profile,
    get_voice_profile,
    save_craft_profile,
)
from .models import (
    CraftProfile,
    ProviderConfig,
    VoiceAnalyzeRequest,
    VoiceAnalyzeResponse,
    VoiceProfile,
)
from .voice_fingerprint import analyze_manuscript_voice

router = APIRouter(prefix="/api")


class VoiceProjectAnalyzeRequest(BaseModel):
    provider: ProviderConfig
    profile_name: str = Field(default="Book voice", min_length=1, max_length=120)


@router.get("/projects/{slug}/craft-profile", response_model=CraftProfile)
def craft_profile(slug: str) -> CraftProfile:
    try:
        return get_craft_profile(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.put("/projects/{slug}/craft-profile", response_model=CraftProfile)
def update_craft_profile(slug: str, payload: CraftProfile) -> CraftProfile:
    try:
        return save_craft_profile(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/voice-profile", response_model=VoiceProfile | None)
def voice_profile(slug: str) -> VoiceProfile | None:
    try:
        return get_voice_profile(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/voice/analyze", response_model=VoiceAnalyzeResponse)
async def analyze_voice_sample(slug: str, payload: VoiceAnalyzeRequest) -> VoiceAnalyzeResponse:
    try:
        profile = await analyze_voice(
            slug,
            sample_text=payload.sample_text,
            provider=payload.provider,
            profile_name=payload.profile_name,
        )
        return VoiceAnalyzeResponse(profile=profile, saved_path=VOICE_PROFILE_PATH)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/{slug}/voice/analyze-project")
async def analyze_project_voice(slug: str, payload: VoiceProjectAnalyzeRequest) -> dict:
    try:
        profile, sources = await analyze_manuscript_voice(
            slug,
            provider=payload.provider,
            profile_name=payload.profile_name,
        )
        return {
            "profile": profile.model_dump(),
            "saved_path": VOICE_PROFILE_PATH,
            "source_files": sources,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
