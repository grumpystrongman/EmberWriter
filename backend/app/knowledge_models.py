from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import ProviderConfig

KnowledgeCategory = Literal["grammar", "publishing"]


class KnowledgeSource(BaseModel):
    id: str
    category: KnowledgeCategory
    authority: str
    title: str
    url: str
    refresh_days: int = Field(ge=1, le=365)
    last_checked_at: str | None = None
    last_success_at: str | None = None
    content_hash: str = ""
    status: Literal["seeded", "current", "stale", "error", "never_checked"] = "never_checked"
    error: str = ""
    chunks: int = 0


class KnowledgeChunk(BaseModel):
    id: str
    source_id: str
    category: KnowledgeCategory
    authority: str
    source_title: str
    source_url: str
    title: str
    body: str
    checked_at: str | None = None
    score: float = 0.0
    semantic_score: float | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    categories: list[KnowledgeCategory] = Field(default_factory=list)
    limit: int = Field(default=12, ge=1, le=50)
    semantic: bool = False
    embedding: "EmbeddingConfig | None" = None


class EmbeddingConfig(BaseModel):
    provider: Literal["ollama", "openai_compatible"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = ""
    api_key: str | None = None


class KnowledgeRefreshResult(BaseModel):
    source_id: str
    status: Literal["updated", "unchanged", "error"]
    chunks: int = 0
    checked_at: str
    error: str = ""


class KnowledgeRefreshResponse(BaseModel):
    checked: int
    updated: int
    unchanged: int
    failed: int
    results: list[KnowledgeRefreshResult] = Field(default_factory=list)


class KnowledgeEmbeddingRequest(BaseModel):
    embedding: EmbeddingConfig
    categories: list[KnowledgeCategory] = Field(default_factory=list)
    force: bool = False


class KnowledgeEmbeddingResponse(BaseModel):
    model: str
    chunks_indexed: int
    dimensions: int


class GrammarReviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)
    provider: ProviderConfig
    context: str = Field(default="", max_length=4000)


class GrammarIssue(BaseModel):
    quote: str
    rule_ids: list[str] = Field(default_factory=list)
    explanation: str
    suggestion: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    intentional_style_possible: bool = False


class GrammarReviewResponse(BaseModel):
    summary: str
    issues: list[GrammarIssue] = Field(default_factory=list)
    rules: list[KnowledgeChunk] = Field(default_factory=list)


class KnowledgeAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    category: KnowledgeCategory = "publishing"
    provider: ProviderConfig


class KnowledgeAnswerResponse(BaseModel):
    answer: str
    rules: list[KnowledgeChunk] = Field(default_factory=list)
