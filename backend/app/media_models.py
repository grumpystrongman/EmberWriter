from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import ProviderConfig


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


VisualCanonStatus = Literal["reference", "concept", "canonical"]


class VisualPromptRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=240)
    kind: str = Field(default="location", min_length=1, max_length=80)
    instruction: str = Field(default="", max_length=6000)
    chapter: int = Field(default=0, ge=0, le=1_000_000)
    provider: ProviderConfig


class VisualPromptResponse(BaseModel):
    prompt: str
    negative_prompt: str = ""
    continuity_notes: list[str] = Field(default_factory=list)
    context_sources: list[str] = Field(default_factory=list)


class VisualAssetGenerateRequest(BaseModel):
    asset_id: str = Field(
        min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    title: str = Field(min_length=1, max_length=240)
    kind: str = Field(default="location", min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=16000)
    negative_prompt: str = Field(default="", max_length=8000)
    base_url: str = "http://127.0.0.1:7860"
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=768, ge=256, le=2048)
    steps: int = Field(default=30, ge=5, le=100)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=30.0)
    sampler_name: str | None = None
    seed: int = -1
    canon_status: VisualCanonStatus = "concept"
    linked_entities: list[str] = Field(default_factory=list, max_length=50)
    reference_asset_id: str | None = Field(
        default=None, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    denoising_strength: float = Field(default=0.45, ge=0.05, le=1.0)


class VisualAssetUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    kind: str | None = Field(default=None, min_length=1, max_length=80)
    canon_status: VisualCanonStatus | None = None
    linked_entities: list[str] | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)
    reference_asset_id: str | None = Field(default=None, max_length=120)


class VisualAssetResponse(BaseModel):
    asset_id: str
    title: str
    kind: str
    relative_path: str
    source: str
    prompt: str = ""
    negative_prompt: str = ""
    width: int
    height: int
    generated_at: str
    canon_status: VisualCanonStatus = "concept"
    linked_entities: list[str] = Field(default_factory=list)
    notes: str = ""
    reference_asset_id: str | None = None
