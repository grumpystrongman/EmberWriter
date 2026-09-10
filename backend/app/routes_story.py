from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from .models import ScenePlanRequest, ScenePlanResponse, StoryIntelligenceResponse
from .scene_architect import create_scene_plan
from .story_intelligence import build_story_intelligence

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/story-intelligence", response_model=StoryIntelligenceResponse)
def story_intelligence(slug: str) -> dict:
    try:
        return build_story_intelligence(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/scene-plan", response_model=ScenePlanResponse)
async def scene_plan(slug: str, payload: ScenePlanRequest) -> dict:
    try:
        return await create_scene_plan(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or active manuscript file not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
