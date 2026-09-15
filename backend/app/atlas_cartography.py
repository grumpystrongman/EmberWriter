from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path
from typing import Any, Iterable

from .atlas import load_atlas, save_atlas
from .atlas_models import (
    AtlasCartographicFeature,
    AtlasFantasyGenerateRequest,
    AtlasFantasyGenerateResponse,
    AtlasGeographySuggestRequest,
    AtlasGeographySuggestResponse,
    AtlasGeoJsonImportRequest,
    AtlasGeoJsonImportResponse,
    AtlasPoint,
    StoryAtlas,
)
from .generation import build_messages, generate
from .memory import list_memory
from .storage import project_root, slugify

_TEXT_EXTENSIONS = {".md", ".txt"}
_SKIP_PARTS = {"assets", ".git", "node_modules", "dist", "build", "__pycache__"}


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


def _unique_feature_id(atlas: StoryAtlas, base: str) -> str:
    existing = {item.id for item in atlas.features}
    stem = slugify(base)[:100] or "feature"
    candidate = stem
    index = 2
    while candidate in existing:
        candidate = f"{stem[:94]}-{index}"
        index += 1
    return candidate


def _bounded_manuscript_sources(slug: str, limit: int = 80000) -> list[dict[str, str]]:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    sources: list[dict[str, str]] = []
    remaining = limit
    for path in sorted(root.rglob("*")):
        if remaining <= 0 or not path.is_file() or path.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_PARTS for part in relative.parts):
            continue
        # Atlas/world reference notes are useful, but prioritize manuscript/draft text by scanning all text files.
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.strip():
            continue
        clipped = text[: min(12000, remaining)]
        remaining -= len(clipped)
        sources.append({"path": relative.as_posix(), "content": clipped})
    return sources


def _memory_context(slug: str) -> list[dict[str, Any]]:
    facts = list_memory(
        slug,
        kinds=["location", "timeline", "thread", "canon", "character_state"],
        limit=500,
    )
    return [
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


def _coerce_points(raw: Any, geometry_type: str) -> list[AtlasPoint]:
    if not isinstance(raw, list):
        return []
    points: list[AtlasPoint] = []
    for item in raw[:5000]:
        try:
            if isinstance(item, dict):
                x, y = float(item.get("x")), float(item.get("y"))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                x, y = float(item[0]), float(item[1])
            else:
                continue
        except (TypeError, ValueError):
            continue
        points.append(AtlasPoint(x=max(-100000, min(100000, x)), y=max(-100000, min(100000, y))))
    minimum = {"point": 1, "line": 2, "polygon": 3}.get(geometry_type, 99)
    return points if len(points) >= minimum else []


async def suggest_geography(slug: str, request: AtlasGeographySuggestRequest) -> AtlasGeographySuggestResponse:
    atlas = load_atlas(slug)
    if request.scope_id and request.scope_id not in {item.id for item in atlas.locations}:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    manuscript = _bounded_manuscript_sources(slug)
    trusted_paths = {item["path"] for item in manuscript}
    compact_locations = [
        {"id": item.id, "name": item.name, "kind": item.kind, "x": item.x, "y": item.y, "region": item.region, "tags": item.tags}
        for item in atlas.locations
    ]
    context = (
        "EXISTING ATLAS LOCATIONS\n"
        + json.dumps(compact_locations, ensure_ascii=False)
        + "\n\nMANUSCRIPT AND WORLD TEXT\n"
        + json.dumps(manuscript, ensure_ascii=False)
        + "\n\nMANUSCRIPT-DERIVED MEMORY\n"
        + json.dumps(_memory_context(slug), ensure_ascii=False)
    )
    instruction = f"""Read the supplied manuscript/world text and propose physical cartographic geometry for the Living Atlas.
The author request is: {request.prompt or 'Infer useful geography from the manuscript without inventing unsupported story facts.'}
Scope location id: {request.scope_id or 'top-level world'}.

Return ONLY JSON shaped as:
{{"features":[{{"name":"...","kind":"coastline|river|road|forest|mountains|wall|district|building|room|shore|border|path|landform","geometry_type":"point|line|polygon","points":[[x,y],...],"source_paths":["path/from/context"],"notes":"why this shape follows from the text"}}],"warnings":["..."]}}

Coordinates use the same relative atlas plane as the existing locations: x increases east and y increases south. Anchor proposed geometry around existing location coordinates where possible. Use polygons for areas/boundaries, lines for rivers/roads/walls/ranges, and points only for isolated landmarks. Do not copy an existing published fantasy map. Do not promote suggestions to canon. If the manuscript is ambiguous, make a restrained suggestion and explain the uncertainty in notes. Prefer a smaller number of useful features over decorative noise."""
    text = await generate(
        request.provider,
        build_messages("brainstorm", instruction, context),
        temperature=0.55,
        top_p=0.88,
        json_mode=True,
    )
    payload = _json_object(text)
    if payload is None:
        raise ValueError("Geography suggestion model did not return structured JSON")
    added = 0
    for raw in payload.get("features", [])[: request.max_features]:
        if not isinstance(raw, dict):
            continue
        geometry_type = str(raw.get("geometry_type", "")).strip().lower()
        if geometry_type not in {"point", "line", "polygon"}:
            continue
        points = _coerce_points(raw.get("points"), geometry_type)
        if not points:
            continue
        name = str(raw.get("name", "Geography suggestion")).strip()[:200] or "Geography suggestion"
        sources = [str(item) for item in raw.get("source_paths", []) if str(item) in trusted_paths][:50]
        atlas.features.append(
            AtlasCartographicFeature(
                id=_unique_feature_id(atlas, f"suggested-{name}"),
                name=name,
                kind=str(raw.get("kind", "landform"))[:80] or "landform",
                geometry_type=geometry_type,
                points=points,
                scope_id=request.scope_id,
                layer=0,
                canon_status="suggested",
                confidence=0.72 if sources else 0.5,
                source="manuscript-ai",
                source_paths=sources,
                notes=str(raw.get("notes", ""))[:4000],
            )
        )
        added += 1
    save_atlas(slug, atlas)
    warnings = [str(item) for item in payload.get("warnings", []) if str(item).strip()]
    if not manuscript:
        warnings.append("No manuscript text files were available; suggestions relied on atlas memory/context only.")
    return AtlasGeographySuggestResponse(atlas=atlas, added_features=added, warnings=warnings)


def _walk_geojson_geometries(payload: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    kind = payload.get("type")
    if kind == "FeatureCollection":
        for feature in payload.get("features", []):
            if isinstance(feature, dict):
                yield from _walk_geojson_geometries(feature)
        return
    if kind == "Feature":
        geometry = payload.get("geometry")
        if isinstance(geometry, dict):
            yield geometry, payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
        return
    if kind in {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}:
        yield payload, {}


def _coordinate_sequences(geometry: dict[str, Any]) -> list[tuple[str, list[list[float]]]]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Point" and isinstance(coordinates, list):
        return [("point", [coordinates])]
    if kind == "LineString" and isinstance(coordinates, list):
        return [("line", coordinates)]
    if kind == "Polygon" and isinstance(coordinates, list) and coordinates:
        return [("polygon", coordinates[0])]
    if kind == "MultiPoint" and isinstance(coordinates, list):
        return [("point", [item]) for item in coordinates]
    if kind == "MultiLineString" and isinstance(coordinates, list):
        return [("line", item) for item in coordinates if isinstance(item, list)]
    if kind == "MultiPolygon" and isinstance(coordinates, list):
        return [("polygon", item[0]) for item in coordinates if isinstance(item, list) and item]
    return []


def _geo_kind(properties: dict[str, Any], geometry_type: str) -> str:
    joined = " ".join(str(properties.get(key, "")) for key in ("natural", "waterway", "highway", "building", "landuse", "place", "boundary", "amenity")).lower()
    if "river" in joined or "stream" in joined or "water" in joined:
        return "river" if geometry_type == "line" else "water"
    if "forest" in joined or "wood" in joined:
        return "forest"
    if "road" in joined or "street" in joined or "path" in joined or properties.get("highway"):
        return "road"
    if properties.get("building"):
        return "building"
    if properties.get("boundary"):
        return "border"
    return "real-geography"


def import_geojson(slug: str, request: AtlasGeoJsonImportRequest) -> AtlasGeoJsonImportResponse:
    atlas = load_atlas(slug)
    if request.scope_id and request.scope_id not in {item.id for item in atlas.locations}:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    raw_parts: list[tuple[str, list[list[float]], dict[str, Any]]] = []
    all_coords: list[tuple[float, float]] = []
    skipped = 0
    for geometry, properties in _walk_geojson_geometries(request.geojson):
        parts = _coordinate_sequences(geometry)
        if not parts:
            skipped += 1
        for geometry_type, sequence in parts:
            clean: list[list[float]] = []
            for coord in sequence[:5000]:
                try:
                    lon, lat = float(coord[0]), float(coord[1])
                except (TypeError, ValueError, IndexError):
                    continue
                clean.append([lon, lat])
                all_coords.append((lon, lat))
            minimum = {"point": 1, "line": 2, "polygon": 3}[geometry_type]
            if len(clean) >= minimum:
                raw_parts.append((geometry_type, clean, properties))
            else:
                skipped += 1
    if not raw_parts or not all_coords:
        raise ValueError("GeoJSON contains no supported Point, LineString or Polygon geometry")
    min_lon = min(item[0] for item in all_coords)
    max_lon = max(item[0] for item in all_coords)
    min_lat = min(item[1] for item in all_coords)
    max_lat = max(item[1] for item in all_coords)
    mid_lat = (min_lat + max_lat) / 2
    lon_scale = max(0.05, math.cos(math.radians(mid_lat)))
    span_x = max(1e-9, (max_lon - min_lon) * lon_scale)
    span_y = max(1e-9, max_lat - min_lat)
    scale = min(900 / span_x, 650 / span_y)
    center_x = 0.0
    center_y = 0.0
    if request.scope_id:
        scope = next(item for item in atlas.locations if item.id == request.scope_id)
        center_x, center_y = scope.x, scope.y
    if request.replace_imported:
        atlas.features = [item for item in atlas.features if not (item.source == "geojson" and item.scope_id == request.scope_id)]
    added = 0
    for index, (geometry_type, sequence, properties) in enumerate(raw_parts):
        points = [
            AtlasPoint(
                x=center_x + (((lon - (min_lon + max_lon) / 2) * lon_scale) * scale),
                y=center_y - ((lat - (min_lat + max_lat) / 2) * scale),
            )
            for lon, lat in sequence
        ]
        name = str(properties.get("name") or properties.get("ref") or f"Imported feature {index + 1}")[:200]
        atlas.features.append(
            AtlasCartographicFeature(
                id=_unique_feature_id(atlas, f"geo-{name}-{index + 1}"),
                name=name,
                kind=_geo_kind(properties, geometry_type),
                geometry_type=geometry_type,
                points=points,
                scope_id=request.scope_id,
                layer=0,
                canon_status="inferred",
                confidence=0.95,
                source="geojson",
                source_ref=request.source_name,
                source_crs="EPSG:4326",
                notes="Imported real-world geography. Review and promote to canon if appropriate for this story.",
                properties={
                    str(key): value
                    for key, value in properties.items()
                    if isinstance(value, (str, int, float, bool))
                },
            )
        )
        added += 1
    save_atlas(slug, atlas)
    return AtlasGeoJsonImportResponse(atlas=atlas, added_features=added, skipped_features=skipped)


def _polar_polygon(rng: random.Random, cx: float, cy: float, rx: float, ry: float, count: int) -> list[AtlasPoint]:
    points: list[AtlasPoint] = []
    phases = [rng.random() * math.tau for _ in range(3)]
    for index in range(count):
        angle = math.tau * index / count
        noise = 1.0
        noise += 0.18 * math.sin(angle * 3 + phases[0])
        noise += 0.10 * math.sin(angle * 7 + phases[1])
        noise += 0.06 * math.sin(angle * 13 + phases[2])
        noise += rng.uniform(-0.045, 0.045)
        points.append(AtlasPoint(x=cx + math.cos(angle) * rx * noise, y=cy + math.sin(angle) * ry * noise))
    return points


def _feature(atlas: StoryAtlas, *, name: str, kind: str, geometry_type: str, points: list[AtlasPoint], scope_id: str, layer: int, notes: str, source: str = "generated-fantasy") -> AtlasCartographicFeature:
    return AtlasCartographicFeature(
        id=_unique_feature_id(atlas, f"generated-{name}"),
        name=name,
        kind=kind,
        geometry_type=geometry_type,  # type: ignore[arg-type]
        points=points,
        scope_id=scope_id,
        layer=layer,
        canon_status="suggested",
        confidence=0.5,
        source=source,
        notes=notes,
    )


def generate_fantasy_geography(slug: str, request: AtlasFantasyGenerateRequest) -> AtlasFantasyGenerateResponse:
    atlas = load_atlas(slug)
    if request.scope_id and request.scope_id not in {item.id for item in atlas.locations}:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    rng = random.Random(request.seed)
    if request.replace_generated:
        atlas.features = [item for item in atlas.features if not (item.source == "generated-fantasy" and item.scope_id == request.scope_id)]
    center_x = 0.0
    center_y = 0.0
    if request.scope_id:
        scope = next(item for item in atlas.locations if item.id == request.scope_id)
        center_x, center_y = scope.x, scope.y
    added = 0
    continent_centers: list[tuple[float, float, float, float]] = []
    for index in range(request.continents):
        spread = 540 if request.continents > 1 else 0
        cx = center_x + (index - (request.continents - 1) / 2) * spread + rng.uniform(-80, 80)
        cy = center_y + rng.uniform(-100, 100)
        rx = rng.uniform(280, 430) / max(1, math.sqrt(request.continents * 0.75))
        ry = rng.uniform(210, 340)
        continent_centers.append((cx, cy, rx, ry))
        coast = _polar_polygon(rng, cx, cy, rx, ry, 48 + request.detail * 12)
        atlas.features.append(_feature(atlas, name=f"Continent {index + 1}", kind="continent", geometry_type="polygon", points=coast, scope_id=request.scope_id, layer=-20, notes="Procedurally generated classic epic-fantasy landmass; reshape and rename before promoting to canon."))
        added += 1

        mountain_count = 1 + request.detail // 2
        for ridge_index in range(mountain_count):
            angle = rng.uniform(-0.9, 0.9)
            length = rx * rng.uniform(0.7, 1.15)
            start_x = cx - math.cos(angle) * length / 2 + rng.uniform(-rx * 0.15, rx * 0.15)
            start_y = cy - math.sin(angle) * length / 2 + rng.uniform(-ry * 0.25, ry * 0.25)
            ridge = [
                AtlasPoint(
                    x=start_x + math.cos(angle) * length * step / 9 + rng.uniform(-18, 18),
                    y=start_y + math.sin(angle) * length * step / 9 + math.sin(step * 1.3) * 18 + rng.uniform(-12, 12),
                )
                for step in range(10)
            ]
            atlas.features.append(_feature(atlas, name=f"Mountain Range {index + 1}.{ridge_index + 1}", kind="mountains", geometry_type="line", points=ridge, scope_id=request.scope_id, layer=-5, notes="Generated mountain spine for classic fantasy cartography."))
            added += 1

        river_count = 1 + request.detail
        for river_index in range(river_count):
            angle = rng.uniform(0, math.tau)
            source_x = cx + math.cos(angle) * rx * rng.uniform(0.05, 0.25)
            source_y = cy + math.sin(angle) * ry * rng.uniform(0.05, 0.25)
            mouth_angle = angle + rng.uniform(-0.7, 0.7)
            mouth_x = cx + math.cos(mouth_angle) * rx * 0.9
            mouth_y = cy + math.sin(mouth_angle) * ry * 0.9
            river = [
                AtlasPoint(
                    x=source_x + (mouth_x - source_x) * step / 7 + math.sin(step * 1.8 + river_index) * 16,
                    y=source_y + (mouth_y - source_y) * step / 7 + math.cos(step * 1.4 + river_index) * 12,
                )
                for step in range(8)
            ]
            atlas.features.append(_feature(atlas, name=f"River {index + 1}.{river_index + 1}", kind="river", geometry_type="line", points=river, scope_id=request.scope_id, layer=-4, notes="Generated drainage line; adjust to fit manuscript geography."))
            added += 1

        forest_count = max(1, request.detail - 1)
        for forest_index in range(forest_count):
            fx = cx + rng.uniform(-rx * 0.5, rx * 0.5)
            fy = cy + rng.uniform(-ry * 0.45, ry * 0.45)
            forest = _polar_polygon(rng, fx, fy, rng.uniform(55, 110), rng.uniform(40, 90), 18)
            atlas.features.append(_feature(atlas, name=f"Forest {index + 1}.{forest_index + 1}", kind="forest", geometry_type="polygon", points=forest, scope_id=request.scope_id, layer=-3, notes="Generated forest region; intended as editable suggested geography."))
            added += 1

    # Add a few route-like cartographic roads between continent centers or across a single landmass.
    if continent_centers:
        for index, (cx, cy, rx, _) in enumerate(continent_centers):
            road = [
                AtlasPoint(x=cx - rx * 0.55, y=cy + math.sin(step * 1.2) * 24),
                AtlasPoint(x=cx - rx * 0.15, y=cy - 30),
                AtlasPoint(x=cx + rx * 0.2, y=cy + 20),
                AtlasPoint(x=cx + rx * 0.58, y=cy - 15),
            ]
            atlas.features.append(_feature(atlas, name=f"Old Road {index + 1}", kind="road", geometry_type="line", points=road, scope_id=request.scope_id, layer=2, notes="Generated visual road only; it does not create a story route connection until the author chooses to do so."))
            added += 1
    save_atlas(slug, atlas)
    return AtlasFantasyGenerateResponse(atlas=atlas, added_features=added, seed=request.seed)
