from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import ProviderConfig

ReaderPersona = Literal["fan", "casual_reader", "strong_editor"]
ReaderStatus = Literal["reading", "ready_to_synthesize", "completed"]


class ReaderRunCreate(BaseModel):
    persona: ReaderPersona
    genre: str = Field(default="General fiction", min_length=1, max_length=120)
    focus: str = Field(default="", max_length=2000)


class ReaderStepRequest(BaseModel):
    provider: ProviderConfig


class ReaderChapterNote(BaseModel):
    id: str
    path: str
    binder_node_id: str | None = None
    position: int = Field(ge=0)
    chapter_title: str
    reaction: str
    engagement: int = Field(ge=1, le=10)
    pacing: int = Field(ge=1, le=10)
    clarity: int = Field(ge=1, le=10)
    emotional_impact: int = Field(ge=1, le=10)
    favorite_moment: str = ""
    confusion: list[str] = Field(default_factory=list)
    predictions: list[str] = Field(default_factory=list)
    character_reactions: list[str] = Field(default_factory=list)
    keep_reading: str = ""
    craft_notes: list[str] = Field(default_factory=list)
    source_hash: str
    stale: bool = False


class ReaderVerdict(BaseModel):
    overall_reaction: str
    score: int = Field(ge=1, le=10)
    audience_fit: str = ""
    genre_fit: str = ""
    strongest_elements: list[str] = Field(default_factory=list)
    weakest_elements: list[str] = Field(default_factory=list)
    character_feedback: list[str] = Field(default_factory=list)
    pacing_feedback: list[str] = Field(default_factory=list)
    plot_feedback: list[str] = Field(default_factory=list)
    voice_feedback: list[str] = Field(default_factory=list)
    ending_feedback: list[str] = Field(default_factory=list)
    unresolved_confusion: list[str] = Field(default_factory=list)
    fulfilled_predictions: list[str] = Field(default_factory=list)
    broken_promises: list[str] = Field(default_factory=list)
    top_revisions: list[str] = Field(default_factory=list)
    would_recommend: str = ""


class ReaderRun(BaseModel):
    id: str
    created_at: str
    updated_at: str
    persona: ReaderPersona
    persona_name: str
    genre: str
    focus: str = ""
    status: ReaderStatus
    current_index: int = Field(ge=0)
    total_documents: int = Field(ge=0)
    notes: list[ReaderChapterNote] = Field(default_factory=list)
    verdict: ReaderVerdict | None = None
    stale_documents: int = Field(default=0, ge=0)


class ReaderStepResponse(BaseModel):
    run: ReaderRun
    action: Literal["chapter_read", "synthesized"]
    chapter_note: ReaderChapterNote | None = None


class ReaderPersonaDefinition(BaseModel):
    id: ReaderPersona
    name: str
    description: str
    lens: list[str] = Field(default_factory=list)


class ReaderRunSummary(BaseModel):
    id: str
    created_at: str
    updated_at: str
    persona: ReaderPersona
    persona_name: str
    genre: str
    focus: str
    status: ReaderStatus
    current_index: int
    total_documents: int
    score: int | None = None
    stale_documents: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
