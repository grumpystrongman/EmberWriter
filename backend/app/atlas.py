from __future__ import annotations

import heapq
import json
import math
import re
from pathlib import Path
from typing import Any

from .atlas_models import (
    AtlasAdviceIdea,
    AtlasAdviceRequest,
    AtlasAdviceResponse,
    AtlasBootstrapRequest,
    AtlasBootstrapResponse,
    AtlasConnection,
    AtlasLocation,
    AtlasPreference,
    AtlasRouteCompareRequest,
    AtlasRouteCompareResponse,
    AtlasRouteRequest,
    AtlasRouteResult,
    AtlasRouteSegment,
    StoryAtlas,
)
from .generation import build_messages, generate
from .memory import list_memory
from .storage import _touch_project, project_root, slugify

ATLAS_PATH = Path("world") / "atlas.json"


def _atlas_file(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root / ATLAS_PATH


def load_atlas(slug: str) -> StoryAtlas:
    path = _atlas_file(slug)
    if not path.exists():
        return StoryAtlas()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("world/atlas.json contains invalid JSON") from exc
    return StoryAtlas.model_validate(payload)


def save_atlas(slug: str, atlas: StoryAtlas) -> StoryAtlas:
    path = _atlas_file(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = StoryAtlas.model_validate(atlas.model_dump(mode="json"))
    temp = path.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(normalized.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(path)
    _touch_project(slug)
    return normalized


def _connection_is_open(atlas: StoryAtlas, connection: AtlasConnection, chapter: int) -> bool:
    if chapter < connection.active_from_chapter:
        return False
    if connection.active_until_chapter is not None and chapter > connection.active_until_chapter:
        return False
    opened = True
    for event in sorted(atlas.events, key=lambda item: (item.chapter, item.id)):
        if event.chapter > chapter or event.target_id != connection.id:
            continue
        if event.action == "connection_close":
            opened = False
        elif event.action == "connection_open":
            opened = True
    return opened


def _known_to(character: str, known_by: list[str]) -> bool:
    if not character.strip() or not known_by:
        return True
    needle = character.casefold().strip()
    return any(item.casefold().strip() in {needle, "*", "all"} for item in known_by)


def _location_is_known(atlas: StoryAtlas, location: AtlasLocation, character: str, chapter: int) -> bool:
    if not character.strip():
        return True
    if _known_to(character, location.known_by):
        return True
    needle = character.casefold().strip()
    for event in sorted(atlas.events, key=lambda item: (item.chapter, item.id)):
        if event.chapter > chapter or event.action != "location_reveal" or event.target_id != location.id:
            continue
        recipients = {item.strip().casefold() for item in event.value.split(",") if item.strip()}
        if not recipients or needle in recipients or "*" in recipients or "all" in recipients:
            return True
    return False


def _edge_hours(atlas: StoryAtlas, connection: AtlasConnection, mode: str) -> float:
    profile = atlas.travel_profiles.get(mode)
    if profile is None:
        raise ValueError(f"Unknown travel mode: {mode}")
    multiplier = connection.mode_multipliers.get(mode, 1.0)
    if multiplier <= 0:
        raise ValueError(f"Connection {connection.id} does not support {mode}")
    return (connection.distance / profile.speed_mph) * connection.terrain_multiplier * multiplier


def _edge_cost(hours: float, connection: AtlasConnection, preference: AtlasPreference) -> float:
    if preference == "fastest":
        return hours
    if preference == "safest":
        return hours * (1 + (connection.risk - 1) * 0.38)
    if preference == "dramatic":
        return hours * (1 + (connection.risk - 1) * 0.04) / max(
            0.35, 1 + (connection.drama - 1) * 0.24
        )
    if preference == "lore":
        return hours * (1 + (connection.risk - 1) * 0.05) / max(
            0.35, 1 + (connection.lore - 1) * 0.24
        )
    if preference == "relationship":
        return hours * (1 + (connection.risk - 1) * 0.04) / max(
            0.35, 1 + (connection.relationship - 1) * 0.28
        )
    return hours * (1 + (connection.risk - 1) * 0.10) / max(
        0.45,
        1
        + (connection.drama - 1) * 0.08
        + (connection.lore - 1) * 0.05
        + (connection.relationship - 1) * 0.05,
    )


def _weighted_score(segments: list[AtlasRouteSegment], field: str) -> float:
    if not segments:
        return 0.0
    total_distance = sum(segment.distance for segment in segments)
    if total_distance <= 0:
        return 0.0
    return round(
        sum(segment.distance * float(getattr(segment, field)) for segment in segments)
        / total_distance,
        2,
    )


def calculate_route(atlas: StoryAtlas, request: AtlasRouteRequest) -> AtlasRouteResult:
    locations = {item.id: item for item in atlas.locations}
    if request.origin_id not in locations:
        raise ValueError(f"Unknown origin location: {request.origin_id}")
    if request.destination_id not in locations:
        raise ValueError(f"Unknown destination location: {request.destination_id}")
    if request.origin_id == request.destination_id:
        return AtlasRouteResult(
            preference=request.preference,
            mode=request.mode,
            origin_id=request.origin_id,
            destination_id=request.destination_id,
            chapter=request.chapter,
            character=request.character,
            location_ids=[request.origin_id],
        )
    if request.mode not in atlas.travel_profiles:
        raise ValueError(f"Unknown travel mode: {request.mode}")

    respect_knowledge = request.respect_character_knowledge and bool(request.character.strip())
    adjacency: dict[str, list[tuple[str, AtlasConnection]]] = {
        location_id: [] for location_id in locations
    }
    for connection in atlas.connections:
        if not _connection_is_open(atlas, connection, request.chapter):
            continue
        if respect_knowledge and not _known_to(request.character, connection.known_by):
            continue
        if respect_knowledge and (
            not _location_is_known(
                atlas, locations[connection.from_id], request.character, request.chapter
            )
            or not _location_is_known(
                atlas, locations[connection.to_id], request.character, request.chapter
            )
        ):
            continue
        multiplier = connection.mode_multipliers.get(request.mode, 1.0)
        if multiplier <= 0:
            continue
        adjacency[connection.from_id].append((connection.to_id, connection))
        if connection.bidirectional:
            adjacency[connection.to_id].append((connection.from_id, connection))

    queue: list[tuple[float, str]] = [(0.0, request.origin_id)]
    best: dict[str, float] = {request.origin_id: 0.0}
    previous: dict[str, tuple[str, AtlasConnection]] = {}
    while queue:
        cost, node = heapq.heappop(queue)
        if cost > best.get(node, math.inf):
            continue
        if node == request.destination_id:
            break
        for neighbor, connection in adjacency.get(node, []):
            hours = _edge_hours(atlas, connection, request.mode)
            next_cost = cost + _edge_cost(hours, connection, request.preference)
            if next_cost + 1e-9 < best.get(neighbor, math.inf):
                best[neighbor] = next_cost
                previous[neighbor] = (node, connection)
                heapq.heappush(queue, (next_cost, neighbor))

    if request.destination_id not in previous:
        suffix = f" for {request.character}" if respect_knowledge else ""
        raise ValueError(
            f"No {request.mode} route from {request.origin_id} to {request.destination_id} "
            f"is available in chapter {request.chapter}{suffix}"
        )

    reversed_steps: list[tuple[str, str, AtlasConnection]] = []
    cursor = request.destination_id
    while cursor != request.origin_id:
        parent, connection = previous[cursor]
        reversed_steps.append((parent, cursor, connection))
        cursor = parent
    reversed_steps.reverse()

    segments: list[AtlasRouteSegment] = []
    for from_id, to_id, connection in reversed_steps:
        segments.append(
            AtlasRouteSegment(
                connection_id=connection.id,
                from_id=from_id,
                to_id=to_id,
                name=connection.name,
                distance=round(connection.distance, 3),
                travel_hours=round(_edge_hours(atlas, connection, request.mode), 3),
                risk=connection.risk,
                drama=connection.drama,
                lore=connection.lore,
                relationship=connection.relationship,
            )
        )

    total_distance = sum(segment.distance for segment in segments)
    total_hours = sum(segment.travel_hours for segment in segments)
    hours_per_day = atlas.travel_profiles[request.mode].hours_per_day
    warnings: list[str] = []
    connection_lookup = {item.id: item for item in atlas.connections}
    inferred = [
        segment.connection_id
        for segment in segments
        if connection_lookup[segment.connection_id].canon_status != "canon"
    ]
    if inferred:
        warnings.append("Route uses inferred or suggested geography: " + ", ".join(inferred))

    return AtlasRouteResult(
        preference=request.preference,
        mode=request.mode,
        origin_id=request.origin_id,
        destination_id=request.destination_id,
        chapter=request.chapter,
        character=request.character,
        segments=segments,
        location_ids=[request.origin_id] + [segment.to_id for segment in segments],
        total_distance=round(total_distance, 3),
        total_hours=round(total_hours, 3),
        total_days=round(total_hours / hours_per_day, 3),
        risk_score=_weighted_score(segments, "risk"),
        drama_score=_weighted_score(segments, "drama"),
        lore_score=_weighted_score(segments, "lore"),
        relationship_score=_weighted_score(segments, "relationship"),
        warnings=warnings,
    )


def compare_routes(
    atlas: StoryAtlas, request: AtlasRouteCompareRequest
) -> AtlasRouteCompareResponse:
    routes: list[AtlasRouteResult] = []
    unavailable: list[AtlasPreference] = []
    signatures: set[tuple[str, ...]] = set()
    for preference in request.preferences:
        try:
            route = calculate_route(
                atlas,
                AtlasRouteRequest(
                    origin_id=request.origin_id,
                    destination_id=request.destination_id,
                    mode=request.mode,
                    preference=preference,
                    chapter=request.chapter,
                    character=request.character,
                    respect_character_knowledge=request.respect_character_knowledge,
                ),
            )
        except ValueError:
            unavailable.append(preference)
            continue
        signature = tuple(segment.connection_id for segment in route.segments)
        if signature in signatures:
            route.warnings.append(
                "This preference resolves to the same path as another route option."
            )
        signatures.add(signature)
        routes.append(route)
    return AtlasRouteCompareResponse(
        routes=routes, unavailable_preferences=unavailable
    )


def atlas_state(atlas: StoryAtlas, chapter: int, character: str = "") -> dict[str, Any]:
    controls: dict[str, str] = {}
    notes: list[dict[str, Any]] = []
    location_lookup = {item.id: item for item in atlas.locations}
    location_known = {
        item.id: _location_is_known(atlas, item, character, chapter)
        for item in atlas.locations
    }
    for event in sorted(atlas.events, key=lambda item: (item.chapter, item.id)):
        if event.chapter > chapter:
            continue
        if event.action == "location_control":
            controls[event.target_id] = event.value
        elif event.action == "note":
            notes.append(
                {
                    "id": event.id,
                    "target_id": event.target_id,
                    "chapter": event.chapter,
                    "summary": event.summary,
                    "value": event.value,
                }
            )
    connection_known: dict[str, bool] = {}
    for item in atlas.connections:
        endpoints_known = location_known.get(item.from_id, False) and location_known.get(
            item.to_id, False
        )
        connection_known[item.id] = (
            _known_to(character, item.known_by)
            and endpoints_known
            and item.from_id in location_lookup
            and item.to_id in location_lookup
        )
    return {
        "chapter": chapter,
        "character": character,
        "connection_open": {
            item.id: _connection_is_open(atlas, item, chapter)
            for item in atlas.connections
        },
        "location_known": location_known,
        "connection_known": connection_known,
        "location_control": controls,
        "notes": notes,
    }


def _json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _atlas_context(slug: str, atlas: StoryAtlas, query: str = "") -> str:
    facts = list_memory(
        slug,
        query=query,
        kinds=["location", "timeline", "thread", "canon", "character_state"],
        limit=100,
    )
    compact_facts = [
        {
            "kind": item["kind"],
            "subject": item["subject"],
            "predicate": item["predicate"],
            "object": item["object"],
            "chapter": item["chapter_order"],
            "source": item["source_path"],
        }
        for item in facts
    ]
    compact_atlas = {
        "units": atlas.map.units,
        "locations": [item.model_dump(mode="json") for item in atlas.locations],
        "connections": [item.model_dump(mode="json") for item in atlas.connections],
        "events": [item.model_dump(mode="json") for item in atlas.events],
    }
    return (
        "STORY ATLAS\n"
        + json.dumps(compact_atlas, ensure_ascii=False)
        + "\n\nRELEVANT STORY MEMORY\n"
        + json.dumps(compact_facts, ensure_ascii=False)
    )


async def advise_atlas(slug: str, request: AtlasAdviceRequest) -> AtlasAdviceResponse:
    atlas = load_atlas(slug)
    route_text = "No origin/destination route was requested."
    if request.origin_id and request.destination_id:
        comparison = compare_routes(
            atlas,
            AtlasRouteCompareRequest(
                origin_id=request.origin_id,
                destination_id=request.destination_id,
                mode=request.mode,
                chapter=request.chapter,
                character=request.character,
            ),
        )
        route_text = json.dumps(comparison.model_dump(mode="json"), ensure_ascii=False)
    instruction = f"""The author wants spatial story advice: {request.prompt}

Chapter: {request.chapter}
Character viewpoint/knowledge filter: {request.character or 'omniscient author'}
Requested route preference: {request.preference}
Computed route options: {route_text}

Return ONLY JSON with this shape:
{{
  "summary": "short recommendation",
  "ideas": [{{"title":"...","rationale":"...","story_effect":"...","route_ids":["existing-connection-id"],"proposed_changes":["suggestion only; do not claim it is canon"]}}],
  "continuity_warnings": ["..."]
}}
Offer 2-4 concrete options. Use existing route/location IDs exactly when referencing the atlas. Treat canon as fixed unless the author explicitly asks to change it. Any new geography or world-state change must be labeled as a proposed change, never silently promoted to canon."""
    text = await generate(
        request.provider,
        build_messages(
            "brainstorm", instruction, _atlas_context(slug, atlas, request.prompt)
        ),
        temperature=0.75,
        top_p=0.9,
        json_mode=True,
    )
    payload = _json_object(text)
    if payload is None:
        return AtlasAdviceResponse(
            summary=text,
            continuity_warnings=[
                "The model returned unstructured advice; no atlas changes were applied."
            ],
        )
    ideas: list[AtlasAdviceIdea] = []
    for raw in payload.get("ideas", []):
        if isinstance(raw, dict):
            try:
                ideas.append(AtlasAdviceIdea.model_validate(raw))
            except ValueError:
                continue
    warnings = [
        str(item)
        for item in payload.get("continuity_warnings", [])
        if str(item).strip()
    ]
    return AtlasAdviceResponse(
        summary=str(payload.get("summary", "")).strip(),
        ideas=ideas,
        continuity_warnings=warnings,
    )


def _bounded_world_notes(slug: str) -> list[dict[str, str]]:
    root = project_root(slug) / "world"
    notes: list[dict[str, str]] = []
    if not root.exists():
        return notes
    remaining = 24000
    for path in sorted(root.glob("*.md")):
        if path.name.lower() == "readme.md" or remaining <= 0:
            continue
        content = path.read_text(encoding="utf-8")[: min(6000, remaining)]
        remaining -= len(content)
        notes.append({"path": f"world/{path.name}", "content": content})
    return notes


def _source_supports(source_evidence: dict[str, str], source_path: str, *needles: str) -> bool:
    evidence = source_evidence.get(source_path, "").casefold()
    required = [needle.strip().casefold() for needle in needles if needle.strip()]
    return bool(evidence) and bool(required) and all(needle in evidence for needle in required)


def _connection_signature(
    from_id: str, to_id: str, name: str, bidirectional: bool
) -> tuple[str, str, str, bool]:
    left, right = from_id, to_id
    if bidirectional and right < left:
        left, right = right, left
    return left, right, slugify(name)[:100], bidirectional


async def bootstrap_atlas(
    slug: str, request: AtlasBootstrapRequest
) -> AtlasBootstrapResponse:
    current = StoryAtlas() if request.reset else load_atlas(slug)
    facts = list_memory(
        slug, kinds=["location", "timeline", "canon", "character_state"], limit=500
    )
    fact_payload = [
        {
            "kind": item["kind"],
            "subject": item["subject"],
            "predicate": item["predicate"],
            "object": item["object"],
            "chapter": item["chapter_order"],
            "confidence": item["confidence"],
            "source": item["source_path"],
        }
        for item in facts
    ]
    instruction = """Build a proposed spatial atlas from the supplied manuscript-derived facts and World Bible excerpts.
Return ONLY JSON with keys locations and connections.
locations: [{name, kind, x, y, region, summary, source_paths}]
connections: [{name, from, to, distance, bidirectional, risk, drama, lore, relationship, source_paths}]
Use simple relative coordinates; x increases east, y increases south. Distances are in story miles unless the source explicitly establishes another unit. Never invent a connection merely to make every node connected. If a distance is unknown, use a plausible relative distance but it will be stored as inferred. Only include places that matter spatially. Keep names exactly as the story uses them where possible."""
    world_notes = _bounded_world_notes(slug)
    context = (
        "MEMORY FACTS\n"
        + json.dumps(fact_payload, ensure_ascii=False)
        + "\n\nWORLD BIBLE\n"
        + json.dumps(world_notes, ensure_ascii=False)
    )
    text = await generate(
        request.provider,
        build_messages("brainstorm", instruction, context),
        temperature=0.45,
        top_p=0.85,
        json_mode=True,
    )
    payload = _json_object(text)
    if payload is None:
        raise ValueError("Atlas bootstrap model did not return structured JSON")

    known_names = {item.name.casefold(): item for item in current.locations}
    known_ids = {item.id for item in current.locations}
    added_locations = 0
    source_index: dict[str, list[str]] = {}
    source_evidence: dict[str, str] = {}
    for fact in facts:
        source_path = str(fact.get("source_path", "")).strip()
        evidence = " ".join(
            str(fact.get(key, "")) for key in ("subject", "predicate", "object")
        ).strip()
        if source_path and evidence:
            source_evidence[source_path] = (
                source_evidence.get(source_path, "") + "\n" + evidence
            ).strip()
        for token in {fact["subject"].strip(), fact["object"].strip()}:
            if token and source_path:
                source_index.setdefault(token.casefold(), []).append(source_path)
    for note in world_notes:
        source_path = str(note.get("path", "")).strip()
        if source_path:
            source_evidence[source_path] = str(note.get("content", ""))
    trusted_sources = set(source_evidence)

    raw_locations = (
        payload.get("locations", [])
        if isinstance(payload.get("locations", []), list)
        else []
    )
    for index, raw in enumerate(raw_locations[:1000]):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name or name.casefold() in known_names:
            continue
        base_id = slugify(name)[:100]
        location_id = base_id
        suffix = 2
        while location_id in known_ids:
            location_id = f"{base_id[:95]}-{suffix}"
            suffix += 1
        try:
            x = max(-100000.0, min(100000.0, float(raw.get("x", index * 120))))
            y = max(
                -100000.0,
                min(100000.0, float(raw.get("y", (index % 5) * 120))),
            )
        except (TypeError, ValueError):
            x, y = float(index * 120), float((index % 5) * 120)
        matched_sources: list[str] = []
        for key, paths in source_index.items():
            if name.casefold() in key or key in name.casefold():
                matched_sources.extend(paths)
        raw_sources = (
            raw.get("source_paths", [])
            if isinstance(raw.get("source_paths"), list)
            else []
        )
        matched_sources.extend(
            str(item)
            for item in raw_sources
            if str(item).strip() in trusted_sources
            and _source_supports(source_evidence, str(item).strip(), name)
        )
        matched_sources = list(dict.fromkeys(matched_sources))[:50]
        canon_status = "canon" if matched_sources else "inferred"
        location = AtlasLocation(
            id=location_id,
            name=name,
            kind=str(raw.get("kind", "location"))[:80] or "location",
            x=x,
            y=y,
            region=str(raw.get("region", ""))[:200],
            summary=str(raw.get("summary", ""))[:4000],
            canon_status=canon_status,
            position_status="inferred",
            confidence=0.85 if matched_sources else 0.6,
            source_paths=matched_sources,
        )
        current.locations.append(location)
        known_names[name.casefold()] = location
        known_ids.add(location.id)
        added_locations += 1

    added_connections = 0
    known_connection_ids = {item.id for item in current.connections}
    known_connection_signatures = {
        _connection_signature(item.from_id, item.to_id, item.name, item.bidirectional)
        for item in current.connections
    }
    raw_connections = (
        payload.get("connections", [])
        if isinstance(payload.get("connections", []), list)
        else []
    )
    for raw in raw_connections[:3000]:
        if not isinstance(raw, dict):
            continue
        from_name = str(raw.get("from", "")).strip().casefold()
        to_name = str(raw.get("to", "")).strip().casefold()
        if from_name not in known_names or to_name not in known_names or from_name == to_name:
            continue
        from_id = known_names[from_name].id
        to_id = known_names[to_name].id
        route_name = str(raw.get("name", "Route"))[:200] or "Route"
        bidirectional = bool(raw.get("bidirectional", True))
        signature = _connection_signature(from_id, to_id, route_name, bidirectional)
        if signature in known_connection_signatures:
            continue
        base_id = slugify(route_name + "-" + from_id + "-" + to_id)[:100]
        connection_id = base_id
        suffix = 2
        while connection_id in known_connection_ids:
            connection_id = f"{base_id[:95]}-{suffix}"
            suffix += 1
        try:
            distance = max(
                0.1, min(1_000_000.0, float(raw.get("distance", 10.0)))
            )
        except (TypeError, ValueError):
            distance = 10.0
        sources = (
            raw.get("source_paths", [])
            if isinstance(raw.get("source_paths"), list)
            else []
        )
        trusted_connection_sources = [
            str(item)
            for item in sources
            if str(item).strip() in trusted_sources
            and _source_supports(
                source_evidence,
                str(item).strip(),
                known_names[from_name].name,
                known_names[to_name].name,
            )
        ][:50]

        def rating(key: str, default: int) -> int:
            try:
                return max(1, min(5, int(raw.get(key, default))))
            except (TypeError, ValueError):
                return default

        current.connections.append(
            AtlasConnection(
                id=connection_id,
                from_id=from_id,
                to_id=to_id,
                name=route_name,
                distance=distance,
                bidirectional=bidirectional,
                risk=rating("risk", 2),
                drama=rating("drama", 2),
                lore=rating("lore", 2),
                relationship=rating("relationship", 1),
                canon_status="inferred",
                confidence=0.65,
                source_paths=trusted_connection_sources,
            )
        )
        known_connection_ids.add(connection_id)
        known_connection_signatures.add(signature)
        added_connections += 1

    current = StoryAtlas.model_validate(current.model_dump(mode="json"))
    save_atlas(slug, current)
    warnings: list[str] = []
    if not facts:
        warnings.append(
            "Story Memory had no spatial facts; bootstrap relied on World Bible material and model inference."
        )
    if added_locations == 0:
        warnings.append("No new locations were found. Existing atlas data was preserved.")
    return AtlasBootstrapResponse(
        atlas=current,
        added_locations=added_locations,
        added_connections=added_connections,
        warnings=warnings,
    )
