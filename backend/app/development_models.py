from __future__ import annotations

from pydantic import BaseModel, Field


class PlotBeat(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    act: str = Field(default="", max_length=120)
    chapter: int = Field(default=0, ge=0, le=10000)
    scene: int = Field(default=0, ge=0, le=10000)
    status: str = Field(default="planned", max_length=80)
    pov: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=8000)
    purpose: str = Field(default="", max_length=4000)
    characters: list[str] = Field(default_factory=list, max_length=30)
    thread_ids: list[str] = Field(default_factory=list, max_length=50)
    source_path: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=8000)


class CharacterArc(BaseModel):
    character: str = Field(min_length=1, max_length=240)
    want: str = Field(default="", max_length=3000)
    need: str = Field(default="", max_length=3000)
    wound: str = Field(default="", max_length=3000)
    lie: str = Field(default="", max_length=3000)
    starting_state: str = Field(default="", max_length=5000)
    midpoint_shift: str = Field(default="", max_length=5000)
    climax_choice: str = Field(default="", max_length=5000)
    ending_state: str = Field(default="", max_length=5000)
    beat_ids: list[str] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=8000)


class RelationshipState(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    participants: list[str] = Field(min_length=2, max_length=8)
    label: str = Field(default="", max_length=240)
    status: str = Field(default="", max_length=1200)
    trust: int = Field(default=0, ge=0, le=5)
    closeness: int = Field(default=0, ge=0, le=5)
    conflict: int = Field(default=0, ge=0, le=5)
    chapter: int = Field(default=0, ge=0, le=10000)
    boundaries: list[str] = Field(default_factory=list, max_length=50)
    milestones: list[str] = Field(default_factory=list, max_length=100)
    unresolved_tension: list[str] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=8000)


class StoryThread(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    kind: str = Field(default="other", max_length=80)
    status: str = Field(default="open", max_length=80)
    introduced_chapter: int = Field(default=0, ge=0, le=10000)
    target_payoff_chapter: int = Field(default=0, ge=0, le=10000)
    setup: str = Field(default="", max_length=6000)
    payoff: str = Field(default="", max_length=6000)
    participants: list[str] = Field(default_factory=list, max_length=30)
    beat_ids: list[str] = Field(default_factory=list, max_length=100)
    source_paths: list[str] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=8000)


class DevelopmentState(BaseModel):
    schema_version: int = 1
    beats: list[PlotBeat] = Field(default_factory=list, max_length=2000)
    character_arcs: list[CharacterArc] = Field(default_factory=list, max_length=500)
    relationships: list[RelationshipState] = Field(default_factory=list, max_length=1000)
    threads: list[StoryThread] = Field(default_factory=list, max_length=2000)
    updated_at: str = ""
