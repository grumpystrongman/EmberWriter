from __future__ import annotations

from typing import Any, Literal

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


class AnalyzeRequest(BaseModel):
    path: str = Field(min_length=1)
    provider: ProviderConfig
    force: bool = False


class AnalyzeResponse(BaseModel):
    path: str
    summary: str
    facts_written: int
    skipped: bool


class MemoryFact(BaseModel):
    id: str
    kind: str
    subject: str
    predicate: str
    object: str
    source_path: str
    confidence: float
    importance: int
    chapter_order: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    score: float


class MemoryStats(BaseModel):
    facts: int
    documents: int
    by_kind: dict[str, int]


class CharacterFact(BaseModel):
    kind: str
    predicate: str
    object: str
    source_path: str
    confidence: float
    importance: int
    chapter_order: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterProfile(BaseModel):
    name: str
    dossier_path: str | None = None
    state: list[CharacterFact] = Field(default_factory=list)
    knowledge: list[CharacterFact] = Field(default_factory=list)
    relationships: list[CharacterFact] = Field(default_factory=list)
    other_facts: list[CharacterFact] = Field(default_factory=list)
    latest_chapter: int = 0


class RelationshipEdge(BaseModel):
    source: str
    target: str
    state: str
    detail: str = ""
    source_path: str
    chapter_order: int
    confidence: float
    importance: int


class StoryIntelligenceResponse(BaseModel):
    characters: list[CharacterProfile]
    relationships: list[RelationshipEdge]


class ScenePlanRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    provider: ProviderConfig
    active_file: str | None = None
    pov: str = Field(default="", max_length=120)
    participants: list[str] = Field(default_factory=list, max_length=20)
    location: str = Field(default="", max_length=240)
    desired_heat: str = Field(default="author controlled", max_length=80)
    save: bool = True


class SceneBeat(BaseModel):
    beat: str
    purpose: str = ""
    character_shift: str = ""


class ScenePlan(BaseModel):
    title: str
    pov: str
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    scene_objective: str
    conflict: str
    opening_state: str = ""
    beats: list[SceneBeat] = Field(default_factory=list)
    emotional_arc: str = ""
    relationship_moves: list[str] = Field(default_factory=list)
    reveals: list[str] = Field(default_factory=list)
    continuity_requirements: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)
    intimacy_notes: list[str] = Field(default_factory=list)
    ending_state: str = ""
    next_scene_pressure: str = ""


class ScenePlanResponse(BaseModel):
    plan: ScenePlan
    saved_path: str | None = None
    context_files: list[str] = Field(default_factory=list)
