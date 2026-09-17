from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .model_profiles import profile_catalog
from .ollama_runtime import installed_ollama_models

router = APIRouter(prefix="/api")


class ModelPullRequest(BaseModel):
    base_url: str = Field(default="http://localhost:11434", min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=300)


def _recommended_models() -> set[str]:
    return {str(item["model"]) for item in profile_catalog()}


@router.get("/model-profiles")
async def model_profiles(base_url: str = "http://localhost:11434") -> dict:
    profiles = profile_catalog()
    try:
        installed = await installed_ollama_models(base_url)
    except (httpx.HTTPError, RuntimeError, ValueError):
        installed = []
    installed_folded = {item.casefold() for item in installed}
    for profile in profiles:
        profile["installed"] = str(profile["model"]).casefold() in installed_folded
    return {"profiles": profiles, "installed_models": installed}


@router.post("/models/pull")
async def pull_recommended_model(payload: ModelPullRequest) -> dict:
    if payload.model not in _recommended_models():
        raise HTTPException(
            status_code=400,
            detail="Only EmberWriter's documented recommended models can be installed from this button. Custom models can still be installed with Ollama and selected normally.",
        )

    timeout = httpx.Timeout(connect=15.0, read=3600.0, write=120.0, pool=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                f"{payload.base_url.rstrip('/')}/api/pull",
                json={"model": payload.model, "stream": False},
            )
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Ollama to install the model.") from exc
    except httpx.ReadTimeout as exc:
        raise HTTPException(
            status_code=504,
            detail="The model download did not finish within one hour. Ollama may still be downloading it; refresh the model list before retrying.",
        ) from exc

    if response.status_code >= 400:
        detail = response.text.strip()[:500] or f"HTTP {response.status_code}"
        raise HTTPException(status_code=502, detail=f"Ollama could not install {payload.model}: {detail}")

    return {"installed": payload.model, "models": await installed_ollama_models(payload.base_url)}
