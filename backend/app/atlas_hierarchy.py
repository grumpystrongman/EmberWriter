from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .atlas import load_atlas, save_atlas
from .atlas_models import (
    AtlasBootstrapRequest,
    AtlasBootstrapResponse,
    AtlasConnection,
    AtlasLocation,
)
from .generation import build_messages, generate
from .memory import list_memory
from .storage import project_root, slugify

SPATIAL_SCALES = (
    "cosmos",
    "galaxy",
    "dimension",
    "system",
    "world",
    "continent",
    "nation",
    "country",
    "state",
    "province",
    "county",
    "region",
    "city",
    "district",
    "street",
    "site",
    "facility",
    "building",
    "floor",
    "room",
    "area",
    "object",
)


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


def _bounded_world_notes(slug: str) -> list[dict[str, str]]:
    root = project_root(slug) / "world"
    notes: list[dict[str, str]] = []
    if not root.exists():
        return notes
    remaining = 30000
    for path in sorted(root.glob("*.md")):
        if path.name.lower() == "readme.md" or remaining <= 0:
            continue
        content = path.read_text(encoding="utf-8")[: min(7000, remaining)]
        remaining -= len(content)
        notes.append({"path": f"world/{path.name}", "content": content})
    return notes


def _source_supports(source_evidence: dict[str, str], source_path: str, *needles: str) -> bool:
    evidence = source_evidence.get(source_path, "").casefold()
    required = [needle.strip().casefold() for needle in needles if needle.strip()]
    return bool(evidence) and bool(required) and all(needle in evidence for needle in required)


def _tag_value(location: AtlasLocation, prefix: str) -> str:
    for tag in location.tags:
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return ""


def _with_tag(tags: list[str], prefix: str, value: str) -> list[str]:
    result = [tag for tag in tags if not tag.startswith(prefix)]
    if value:
        result.append(f"{prefix}{value}")
    return result[:60]


def _scale_for(raw_scale: object, kind: str) -> str:
    candidate = str(raw_scale or "").strip().lower().replace(" ", "-")
    if candidate in SPATIAL_SCALES:
        return candidate
    lowered = kind.casefold()
    if re.search(r"room|chamber|office|bedroom|kitchen|classroom|ward|lab", lowered):
        return "room"
    if re.search(r"floor|deck|level|storey|story", lowered):
        return "floor"
    if re.search(r"hospital|school|academy|campus|station|airport|facility", lowered):
        return "facility"
    if re.search(r"house|building|tower|keep|palace|castle|inn|tavern|temple", lowered):
        return "building"
    if re.search(r"street|road|avenue|lane|boulevard", lowered):
        return "street"
    if re.search(r"district|quarter|ward|neighborhood", lowered):
        return "district"
    if re.search(r"city|town|village|settlement", lowered):
        return "city"
    if re.search(r"county", lowered):
        return "county"
    if re.search(r"state", lowered):
        return "state"
    if re.search(r"province", lowered):
        return "province"
    if re.search(r"country", lowered):
        return "country"
    if re.search(r"nation|kingdom|empire|republic", lowered):
        return "nation"
    if re.search(r"continent|landmass", lowered):
        return "continent"
    if re.search(r"planet|world|moon", lowered):
        return "world"
    if re.search(r"system|star", lowered):
        return "system"
    if re.search(r"dimension|realm|plane", lowered):
        return "dimension"
    if re.search(r"galaxy", lowered):
        return "galaxy"
    if re.search(r"cosmos|universe", lowered):
        return "cosmos"
    return "site"


def _safe_basis(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:180]


def _connection_signature(from_id: str, to_id: str, name: str, bidirectional: bool) -> tuple[str, str, str, bool]:
    left, right = from_id, to_id
    if bidirectional and right < left:
        left, right = right, left
    return left, right, slugify(name)[:100], bidirectional


def _would_cycle(child_id: str, parent_id: str, parent_by_id: dict[str, str]) -> bool:
    cursor = parent_id
    seen: set[str] = set()
    while cursor and cursor not in seen:
        if cursor == child_id:
            return True
        seen.add(cursor)
        cursor = parent_by_id.get(cursor, "")
    return False


async def build_spatial_hierarchy(
    slug: str, request: AtlasBootstrapRequest
) -> AtlasBootstrapResponse:
    current = load_atlas(slug) if not request.reset else type(load_atlas(slug))()
    facts = list_memory(
        slug,
        kinds=["location", "timeline", "canon", "character_state"],
        limit=500,
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
    world_notes = _bounded_world_notes(slug)
    current_payload = [
        {
            "name": item.name,
            "kind": item.kind,
            "scale": _tag_value(item, "scale:"),
            "parent_id": _tag_value(item, "parent:"),
            "region": item.region,
            "canon_status": item.canon_status,
            "source_paths": item.source_paths,
        }
        for item in current.locations
    ]

    instruction = f"""Build the novel's SPATIAL WORLD MODEL, not merely a flat fantasy map.
Return ONLY JSON with keys locations and connections.

Allowed spatial scales, broad to granular:
{', '.join(SPATIAL_SCALES)}

locations must use:
[{{name, kind, scale, parent, x, y, region, summary, canon_status, confidence, inference_reason, source_paths}}]
connections must use:
[{{name, from, to, distance, bidirectional, risk, drama, lore, relationship, source_paths}}]

Rules:
1. Work from the most granular manuscript-supported places upward. A bedroom belongs in a floor/building; a building may belong on a street/site; a street belongs in a district/city; a city belongs in a county/region/nation/world when evidence supports those containers.
2. Include container locations needed to make the hierarchy navigable, but do not invent a complete world merely to fill blank levels. Missing levels are allowed.
3. parent is the exact NAME of the immediate containing location. Use an empty parent for genuine top-level places.
4. Coordinates are relative to siblings inside the same parent. x increases east/right; y increases south/down. Do not pretend coordinates are canon unless the manuscript establishes them.
5. canon_status may be canon, inferred, or suggested. Use canon only for an explicitly named/stated place. Use inferred for a conservative spatial conclusion strongly implied by movement or containment. Use suggested for optional author-facing additions.
6. inference_reason must briefly explain why an inferred/suggested place is reasonable. Do not use a reason to smuggle in unsupported canon.
7. Infer only what is structurally necessary or strongly implied. For example, movement from an upstairs bedroom down to a kitchen can justify a stair/hall inference; it does not justify inventing twelve extra rooms, a ballroom, or a cellar.
8. Facilities are first-class containers: schools, hospitals, stations, ships, campuses, prisons, castles, etc. Their children can be buildings, floors/decks, rooms, wards, labs, classrooms, corridors, areas, and meaningful objects.
9. Preserve existing author-created places and names. Enrich missing hierarchy rather than renaming or duplicating them.
10. Only add connections when the story establishes or strongly implies traversability/adjoining movement. Never connect everything just to make a graph.
11. Distances remain story miles in the current route engine. For interiors, omit uncertain connections rather than fabricating precise distances.
12. source_paths must only contain supplied source paths that actually support the location or connection.
13. Prefer meaningful spatial entities an author may need for continuity. Avoid decorative filler.
"""
    context = (
        "EXISTING ATLAS\n"
        + json.dumps(current_payload, ensure_ascii=False)
        + "\n\nMEMORY FACTS\n"
        + json.dumps(fact_payload, ensure_ascii=False)
        + "\n\nWORLD BIBLE\n"
        + json.dumps(world_notes, ensure_ascii=False)
    )
    text = await generate(
        request.provider,
        build_messages("brainstorm", instruction, context),
        temperature=0.35,
        top_p=0.82,
        json_mode=True,
    )
    payload = _json_object(text)
    if payload is None:
        raise ValueError("Spatial hierarchy model did not return structured JSON")

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
        for token in {str(fact.get("subject", "")).strip(), str(fact.get("object", "")).strip()}:
            if token and source_path:
                source_index.setdefault(token.casefold(), []).append(source_path)
    for note in world_notes:
        source_path = str(note.get("path", "")).strip()
        if source_path:
            source_evidence[source_path] = str(note.get("content", ""))
    trusted_sources = set(source_evidence)

    known_names = {item.name.casefold(): item for item in current.locations}
    known_ids = {item.id for item in current.locations}
    raw_locations = payload.get("locations", []) if isinstance(payload.get("locations"), list) else []
    pending_parent_names: dict[str, str] = {}
    added_locations = 0

    for index, raw in enumerate(raw_locations[:1800]):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        kind = str(raw.get("kind", "location"))[:80] or "location"
        scale = _scale_for(raw.get("scale"), kind)
        parent_name = str(raw.get("parent", "")).strip()
        basis = _safe_basis(raw.get("inference_reason"))

        existing = known_names.get(name.casefold())
        if existing is not None:
            if not _tag_value(existing, "scale:"):
                existing.tags = _with_tag(existing.tags, "scale:", scale)
            if parent_name and not _tag_value(existing, "parent:"):
                pending_parent_names[existing.id] = parent_name
            continue

        matched_sources: list[str] = []
        for key, paths in source_index.items():
            if name.casefold() in key or key in name.casefold():
                matched_sources.extend(paths)
        raw_sources = raw.get("source_paths", []) if isinstance(raw.get("source_paths"), list) else []
        matched_sources.extend(
            str(item)
            for item in raw_sources
            if str(item).strip() in trusted_sources
            and _source_supports(source_evidence, str(item).strip(), name)
        )
        matched_sources = list(dict.fromkeys(matched_sources))[:50]

        requested_status = str(raw.get("canon_status", "inferred")).strip().lower()
        if matched_sources:
            canon_status = "canon"
            origin = "manuscript"
        elif requested_status == "suggested":
            canon_status = "suggested"
            origin = "ai-suggestion"
        else:
            canon_status = "inferred"
            origin = "ai-inference"

        try:
            x = max(-100000.0, min(100000.0, float(raw.get("x", index * 120))))
            y = max(-100000.0, min(100000.0, float(raw.get("y", (index % 7) * 100))))
        except (TypeError, ValueError):
            x, y = float(index * 120), float((index % 7) * 100)
        try:
            confidence = float(raw.get("confidence", 0.9 if matched_sources else 0.65))
        except (TypeError, ValueError):
            confidence = 0.9 if matched_sources else 0.65
        confidence = max(0.05, min(1.0, confidence))
        if matched_sources:
            confidence = max(confidence, 0.8)
        elif canon_status == "suggested":
            confidence = min(confidence, 0.6)

        base_id = slugify(name)[:100]
        location_id = base_id
        suffix = 2
        while location_id in known_ids:
            location_id = f"{base_id[:95]}-{suffix}"
            suffix += 1

        tags = [f"scale:{scale}", f"origin:{origin}"]
        if basis:
            tags.append(f"basis:{basis}")
        location = AtlasLocation(
            id=location_id,
            name=name,
            kind=kind,
            x=x,
            y=y,
            region=str(raw.get("region", parent_name))[:200],
            summary=str(raw.get("summary", ""))[:4000],
            tags=tags,
            canon_status=canon_status,
            position_status="inferred" if origin != "author" else "canon",
            confidence=confidence,
            source_paths=matched_sources,
        )
        current.locations.append(location)
        known_names[name.casefold()] = location
        known_ids.add(location.id)
        if parent_name:
            pending_parent_names[location.id] = parent_name
        added_locations += 1

    parent_by_id = {
        item.id: _tag_value(item, "parent:")
        for item in current.locations
        if _tag_value(item, "parent:")
    }
    for child_id, parent_name in pending_parent_names.items():
        child = next((item for item in current.locations if item.id == child_id), None)
        parent = known_names.get(parent_name.casefold())
        if child is None or parent is None or parent.id == child.id:
            continue
        if _would_cycle(child.id, parent.id, parent_by_id):
            continue
        child.tags = _with_tag(child.tags, "parent:", parent.id)
        if not child.region:
            child.region = parent.name
        parent_by_id[child.id] = parent.id

    known_connection_ids = {item.id for item in current.connections}
    known_connection_signatures = {
        _connection_signature(item.from_id, item.to_id, item.name, item.bidirectional)
        for item in current.connections
    }
    raw_connections = payload.get("connections", []) if isinstance(payload.get("connections"), list) else []
    added_connections = 0
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
        try:
            distance = max(0.001, min(1_000_000.0, float(raw.get("distance", 1.0))))
        except (TypeError, ValueError):
            continue
        raw_sources = raw.get("source_paths", []) if isinstance(raw.get("source_paths"), list) else []
        trusted_connection_sources = [
            str(item)
            for item in raw_sources
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

        base_id = slugify(route_name + "-" + from_id + "-" + to_id)[:100]
        connection_id = base_id
        suffix = 2
        while connection_id in known_connection_ids:
            connection_id = f"{base_id[:95]}-{suffix}"
            suffix += 1
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
                confidence=0.7 if trusted_connection_sources else 0.55,
                source_paths=trusted_connection_sources,
            )
        )
        known_connection_ids.add(connection_id)
        known_connection_signatures.add(signature)
        added_connections += 1

    saved = save_atlas(slug, current)
    warnings: list[str] = []
    if not facts:
        warnings.append("Story Memory had no spatial facts; hierarchy relied on World Bible material and conservative inference.")
    if added_locations == 0:
        warnings.append("No new spatial entities were found. Existing hierarchy was preserved and may have been enriched.")
    return AtlasBootstrapResponse(
        atlas=saved,
        added_locations=added_locations,
        added_connections=added_connections,
        warnings=warnings,
    )
