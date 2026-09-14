from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import ProviderConfig

AtlasStatus = Literal["canon", "inferred", "suggested"]
AtlasPreference = Literal["fastest", "safest", "balanced", "dramatic", "lore", "relationship"]
AtlasEventAction = Literal["connection_open", "connection_close", "location_reveal", "location_control", "note"]


class AtlasTravelProfile(BaseModel):
    speed_mph: float = Field(gt=0, le=10000)
    hours_per_day: float = Field(default=8.0, gt=0, le=24)


class AtlasLocation(BaseModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(default="location", max_length=80)
    x: float = Field(default=0.0, ge=-100000, le=100000)
    y: float = Field(default=0.0, ge=-100000, le=100000)
    region: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=4000)
    terrain: list[str] = Field(default_factory=list, max_length=30)
    tags: list[str] = Field(default_factory=list, max_length=60)
    canon_status: AtlasStatus = "canon"
    position_status: AtlasStatus = "inferred"
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_paths: list[str] = Field(default_factory=list, max_length=50)
    known_by: list[str] = Field(default_factory=list, max_length=100)
    image_asset_id: str | None = Field(default=None, max_length=120)


class AtlasConnection(BaseModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    from_id: str = Field(min_length=1, max_length=120)
    to_id: str = Field(min_length=1, max_length=120)
    name: str = Field(default="Route", max_length=200)
    distance: float = Field(gt=0, le=1_000_000)
    bidirectional: bool = True
    mode_multipliers: dict[str, float] = Field(default_factory=dict)
    terrain_multiplier: float = Field(default=1.0, ge=0.1, le=20)
    risk: int = Field(default=2, ge=1, le=5)
    drama: int = Field(default=2, ge=1, le=5)
    lore: int = Field(default=2, ge=1, le=5)
    relationship: int = Field(default=1, ge=1, le=5)
    active_from_chapter: int = Field(default=0, ge=0, le=1_000_000)
    active_until_chapter: int | None = Field(default=None, ge=0, le=1_000_000)
    canon_status: AtlasStatus = "canon"
    confidence: float = Field(default=1.0, ge=0, le=1)
    known_by: list[str] = Field(default_factory=list, max_length=100)
    source_paths: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_window(self) -> "AtlasConnection":
        if self.active_until_chapter is not None and self.active_until_chapter < self.active_from_chapter:
            raise ValueError("active_until_chapter must be greater than or equal to active_from_chapter")
        for mode, multiplier in self.mode_multipliers.items():
            if not mode.strip():
                raise ValueError("Travel mode names cannot be blank")
            if multiplier < 0:
                raise ValueError("Travel mode multipliers cannot be negative")
        return self


class AtlasEvent(BaseModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    chapter: int = Field(ge=0, le=1_000_000)
    action: AtlasEventAction
    target_id: str = Field(min_length=1, max_length=120)
    summary: str = Field(default="", max_length=2000)
    value: str = Field(default="", max_length=500)
    source_path: str = Field(default="", max_length=500)


class AtlasMapConfig(BaseModel):
    title: str = Field(default="Story Atlas", max_length=200)
    units: str = Field(default="miles", max_length=40)
    background_asset_id: str | None = Field(default=None, max_length=120)


_DEFAULT_PROFILES = {
    "walk": AtlasTravelProfile(speed_mph=3.0, hours_per_day=8.0),
    "horse": AtlasTravelProfile(speed_mph=5.0, hours_per_day=9.0),
    "wagon": AtlasTravelProfile(speed_mph=3.5, hours_per_day=8.0),
    "boat": AtlasTravelProfile(speed_mph=4.0, hours_per_day=10.0),
    "airship": AtlasTravelProfile(speed_mph=25.0, hours_per_day=16.0),
    "portal": AtlasTravelProfile(speed_mph=10000.0, hours_per_day=24.0),
}


class StoryAtlas(BaseModel):
    schema_version: int = Field(default=1, ge=1, le=10)
    map: AtlasMapConfig = Field(default_factory=AtlasMapConfig)
    travel_profiles: dict[str, AtlasTravelProfile] = Field(default_factory=lambda: dict(_DEFAULT_PROFILES))
    locations: list[AtlasLocation] = Field(default_factory=list, max_length=5000)
    connections: list[AtlasConnection] = Field(default_factory=list, max_length=10000)
    events: list[AtlasEvent] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def validate_graph(self) -> "StoryAtlas":
        location_ids = [item.id for item in self.locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("Atlas location IDs must be unique")
        connection_ids = [item.id for item in self.connections]
        if len(connection_ids) != len(set(connection_ids)):
            raise ValueError("Atlas connection IDs must be unique")
        event_ids = [item.id for item in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Atlas event IDs must be unique")
        known_locations = set(location_ids)
        known_connections = set(connection_ids)
        for connection in self.connections:
            if connection.from_id == connection.to_id:
                raise ValueError(f"Connection {connection.id} cannot connect a location to itself")
            if connection.from_id not in known_locations or connection.to_id not in known_locations:
                raise ValueError(f"Connection {connection.id} references an unknown location")
        for event in self.events:
            if event.action.startswith("connection_") and event.target_id not in known_connections:
                raise ValueError(f"Event {event.id} references an unknown connection")
            if event.action.startswith("location_") and event.target_id not in known_locations:
                raise ValueError(f"Event {event.id} references an unknown location")
        return self


class AtlasRouteRequest(BaseModel):
    origin_id: str = Field(min_length=1, max_length=120)
    destination_id: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="walk", min_length=1, max_length=80)
    preference: AtlasPreference = "balanced"
    chapter: int = Field(default=0, ge=0, le=1_000_000)
    character: str = Field(default="", max_length=200)
    respect_character_knowledge: bool = True


class AtlasRouteSegment(BaseModel):
    connection_id: str
    from_id: str
    to_id: str
    name: str
    distance: float
    travel_hours: float
    risk: int
    drama: int
    lore: int
    relationship: int


class AtlasRouteResult(BaseModel):
    preference: AtlasPreference
    mode: str
    origin_id: str
    destination_id: str
    chapter: int
    character: str = ""
    segments: list[AtlasRouteSegment] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    total_distance: float = 0.0
    total_hours: float = 0.0
    total_days: float = 0.0
    risk_score: float = 0.0
    drama_score: float = 0.0
    lore_score: float = 0.0
    relationship_score: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class AtlasRouteCompareRequest(BaseModel):
    origin_id: str = Field(min_length=1, max_length=120)
    destination_id: str = Field(min_length=1, max_length=120)
    mode: str = Field(default="walk", min_length=1, max_length=80)
    chapter: int = Field(default=0, ge=0, le=1_000_000)
    character: str = Field(default="", max_length=200)
    respect_character_knowledge: bool = True
    preferences: list[AtlasPreference] = Field(
        default_factory=lambda: ["fastest", "safest", "balanced", "dramatic", "lore", "relationship"],
        min_length=1,
        max_length=6,
    )


class AtlasRouteCompareResponse(BaseModel):
    routes: list[AtlasRouteResult] = Field(default_factory=list)
    unavailable_preferences: list[AtlasPreference] = Field(default_factory=list)


class AtlasAdviceRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    provider: ProviderConfig
    chapter: int = Field(default=0, ge=0, le=1_000_000)
    character: str = Field(default="", max_length=200)
    origin_id: str = Field(default="", max_length=120)
    destination_id: str = Field(default="", max_length=120)
    mode: str = Field(default="walk", max_length=80)
    preference: AtlasPreference = "dramatic"


class AtlasAdviceIdea(BaseModel):
    title: str = "Idea"
    rationale: str = ""
    story_effect: str = ""
    route_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)


class AtlasAdviceResponse(BaseModel):
    summary: str = ""
    ideas: list[AtlasAdviceIdea] = Field(default_factory=list)
    continuity_warnings: list[str] = Field(default_factory=list)


class AtlasBootstrapRequest(BaseModel):
    provider: ProviderConfig
    reset: bool = False


class AtlasBootstrapResponse(BaseModel):
    atlas: StoryAtlas
    added_locations: int = 0
    added_connections: int = 0
    warnings: list[str] = Field(default_factory=list)
