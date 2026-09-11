from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterPortraitGenerateRequest(BaseModel):
    character: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=12000)
    negative_prompt: str = Field(default="", max_length=8000)
    base_url: str = "http://127.0.0.1:7860"
    width: int = Field(default=768, ge=256, le=1536)
    height: int = Field(default=1024, ge=256, le=1536)
    steps: int = Field(default=28, ge=5, le=100)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=30.0)
    sampler_name: str | None = None
    seed: int = -1


class CharacterPortraitResponse(BaseModel):
    character: str
    relative_path: str
    source: str
    prompt: str
    width: int
    height: int
    generated_at: str
