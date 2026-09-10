from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)


class ProjectImport(BaseModel):
    source_path: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


class ProjectSummary(BaseModel):
    slug: str
    name: str
    description: str = ""
    updated_at: str


class ProjectDetail(ProjectSummary):
    files: list[str]
    content_profile: dict


class FilePayload(BaseModel):
    content: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=30)


class SearchHit(BaseModel):
    path: str
    score: float
    excerpt: str


class ProviderConfig(BaseModel):
    provider: Literal["ollama", "openai_compatible"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = ""
    api_key: str | None = None


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    mode: Literal["write", "continue", "rewrite", "brainstorm", "critic", "continuity"] = "write"
    active_file: str | None = None
    selected_text: str | None = None
    provider: ProviderConfig


class GenerateResponse(BaseModel):
    text: str
    context_files: list[str]


class ContextRequest(BaseModel):
    prompt: str = ""
    active_file: str | None = None
    selected_text: str | None = None


class ContextResponse(BaseModel):
    context: str
    files: list[str]
