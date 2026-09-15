from __future__ import annotations

import json
import math
import random
import re
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
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _unique_id(atlas: StoryAtlas, base: str) -> str:
    existing = {item.id for item in atlas.features}
    stem = slugify(base)[:100] or "feature"
    value, index = stem, 2
    while value in existing:
        value = f"{stem[:94]}-{index}"
        index += 1
    return value


def _manuscript_sources(slug: str, limit: int = 80000) -> list[dict[str, str]]:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    remaining = limit
    result: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if remaining <= 0 or not path.is_file() or path.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_PARTS for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.strip():
            continue
        clipped = text[: min(12000, remaining)]
        remaining -= len(clipped)
        result.append({"path": relative.as_posix(), "content": clipped})
    return result


def _memory_context(slug: str) -> list[dict[str, Any]]:
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
        for item in list_memory(
            slug,
            kinds=["location", "timeline", "thread", "canon", "character_state"],
            limit=500,
        )
    ]


def _points(raw: Any, geometry_type: str) -> list[AtlasPoint]:
    if not isinstance(raw, list):
        return []
    result: list[AtlasPoint] = []
    for item in raw[:5000]:
        try:
            if isinstance(item, dict):
                x, y = float(item["x"]), float(item["y"])
            else:
                x, y = float(item[0]), float(item[1])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        result.append(AtlasPoint(x=max(-100000, min(100000, x)), y=max(-100000, min(100000, y))))
    minimum = {"point": 1, "line": 2, "polygon": 3}.get(geometry_type, 999)
    return result if len(result) >= minimum else []


async def suggest_geography(slug: str, request: AtlasGeographySuggestRequest) -> AtlasGeographySuggestResponse:
    atlas = load_atlas(slug)
    known_locations = {item.id for item in atlas.locations}
    if request.scope_id and request.scope_id not in known_locations:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    manuscript = _manuscript_sources(slug)
    trusted_paths = {item["path"] for item in manuscript}
    context = (
        "EXISTING ATLAS LOCATIONS\n"
        + json.dumps(
            [{"id": item.id, "name": item.name, "kind": item.kind, "x": item.x, "y": item.y, "region": item.region, "tags": item.tags} for item in atlas.locations],
            ensure_ascii=False,
        )
        + "\n\nMANUSCRIPT AND WORLD TEXT\n"
        + json.dumps(manuscript, ensure_ascii=False)
        + "\n\nMANUSCRIPT-DERIVED MEMORY\n"
        + json.dumps(_memory_context(slug), ensure_ascii=False)
    )
    instruction = f"""Read the supplied manuscript/world text and propose physical cartographic geometry.
Author request: {request.prompt or 'Infer useful geography without inventing unsupported story facts.'}
Scope: {request.scope_id or 'top-level world'}.
Return ONLY JSON: {{"features":[{{"name":"...","kind":"coastline|river|road|forest|mountains|wall|district|building|room|shore|border|path|landform","geometry_type":"point|line|polygon","points":[[x,y],...],"source_paths":["path/from/context"],"notes":"evidence/uncertainty"}}],"warnings":[]}}.
Coordinates share the existing atlas plane: x east, y south. Anchor shapes around known locations. Use polygons for areas, lines for roads/rivers/walls/ranges. Do not copy any published fantasy map. Everything is a suggestion, never canon."""
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
    raw_features = payload.get("features", [])
    if not isinstance(raw_features, list):
        raw_features = []
    for raw in raw_features[: request.max_features]:
        if not isinstance(raw, dict):
            continue
        geometry_type = str(raw.get("geometry_type", "")).lower()
        if geometry_type not in {"point", "line", "polygon"}:
            continue
        feature_points = _points(raw.get("points"), geometry_type)
        if not feature_points:
            continue
        name = str(raw.get("name", "Geography suggestion"))[:200] or "Geography suggestion"
        raw_sources = raw.get("source_paths", [])
        source_paths = [str(item) for item in raw_sources if str(item) in trusted_paths][:50] if isinstance(raw_sources, list) else []
        atlas.features.append(
            AtlasCartographicFeature(
                id=_unique_id(atlas, f"suggested-{name}"),
                name=name,
                kind=str(raw.get("kind", "landform"))[:80] or "landform",
                geometry_type=geometry_type,
                points=feature_points,
                scope_id=request.scope_id,
                canon_status="suggested",
                confidence=0.72 if source_paths else 0.5,
                source="manuscript-ai",
                source_paths=source_paths,
                notes=str(raw.get("notes", ""))[:4000],
            )
        )
        added += 1
    save_atlas(slug, atlas)
    warnings = [str(item) for item in payload.get("warnings", []) if str(item).strip()] if isinstance(payload.get("warnings"), list) else []
    if not manuscript:
        warnings.append("No manuscript text files were available; suggestions relied on atlas memory/context only.")
    return AtlasGeographySuggestResponse(atlas=atlas, added_features=added, warnings=warnings)


def _geojson_geometries(payload: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    kind = payload.get("type")
    if kind == "FeatureCollection":
        for item in payload.get("features", []):
            if isinstance(item, dict):
                yield from _geojson_geometries(item)
    elif kind == "Feature":
        geometry = payload.get("geometry")
        if isinstance(geometry, dict):
            properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
            yield geometry, properties
    elif kind in {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}:
        yield payload, {}


def _sequences(geometry: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    kind, coordinates = geometry.get("type"), geometry.get("coordinates")
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
    if properties.get("highway") or any(term in joined for term in ("road", "street", "path")):
        return "road"
    if properties.get("building"):
        return "building"
    if properties.get("boundary"):
        return "border"
    return "real-geography"


def import_geojson(slug: str, request: AtlasGeoJsonImportRequest) -> AtlasGeoJsonImportResponse:
    atlas = load_atlas(slug)
    locations = {item.id: item for item in atlas.locations}
    if request.scope_id and request.scope_id not in locations:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    parts: list[tuple[str, list[tuple[float, float]], dict[str, Any]]] = []
    all_coords: list[tuple[float, float]] = []
    skipped = 0
    for geometry, properties in _geojson_geometries(request.geojson):
        sequences = _sequences(geometry)
        if not sequences:
            skipped += 1
        for geometry_type, sequence in sequences:
            clean: list[tuple[float, float]] = []
            for coord in sequence[:5000]:
                try:
                    lon, lat = float(coord[0]), float(coord[1])
                except (IndexError, TypeError, ValueError):
                    continue
                clean.append((lon, lat))
                all_coords.append((lon, lat))
            if len(clean) >= {"point": 1, "line": 2, "polygon": 3}[geometry_type]:
                parts.append((geometry_type, clean, properties))
            else:
                skipped += 1
    if not parts or not all_coords:
        raise ValueError("GeoJSON contains no supported Point, LineString or Polygon geometry")
    min_lon, max_lon = min(x for x, _ in all_coords), max(x for x, _ in all_coords)
    min_lat, max_lat = min(y for _, y in all_coords), max(y for _, y in all_coords)
    mid_lat = (min_lat + max_lat) / 2
    lon_scale = max(0.05, math.cos(math.radians(mid_lat)))
    span_x = max(1e-9, (max_lon - min_lon) * lon_scale)
    span_y = max(1e-9, max_lat - min_lat)
    scale = min(900 / span_x, 650 / span_y)
    center_x = locations[request.scope_id].x if request.scope_id else 0.0
    center_y = locations[request.scope_id].y if request.scope_id else 0.0
    if request.replace_imported:
        atlas.features = [item for item in atlas.features if not (item.source == "geojson" and item.scope_id == request.scope_id)]
    added = 0
    for index, (geometry_type, sequence, properties) in enumerate(parts):
        feature_points = [
            AtlasPoint(
                x=center_x + (lon - (min_lon + max_lon) / 2) * lon_scale * scale,
                y=center_y - (lat - (min_lat + max_lat) / 2) * scale,
            )
            for lon, lat in sequence
        ]
        name = str(properties.get("name") or properties.get("ref") or f"Imported feature {index + 1}")[:200]
        simple_properties = {str(key): value for key, value in properties.items() if isinstance(value, (str, int, float, bool))}
        atlas.features.append(
            AtlasCartographicFeature(
                id=_unique_id(atlas, f"geo-{name}-{index + 1}"),
                name=name,
                kind=_geo_kind(properties, geometry_type),
                geometry_type=geometry_type,
                points=feature_points,
                scope_id=request.scope_id,
                canon_status="inferred",
                confidence=0.95,
                source="geojson",
                source_ref=request.source_name,
                source_crs="EPSG:4326",
                notes="Imported real-world geography. Review and promote to canon if appropriate for this story.",
                properties=simple_properties,
            )
        )
        added += 1
    save_atlas(slug, atlas)
    return AtlasGeoJsonImportResponse(atlas=atlas, added_features=added, skipped_features=skipped)


def _blob(rng: random.Random, cx: float, cy: float, rx: float, ry: float, count: int) -> list[AtlasPoint]:
    phases = [rng.random() * math.tau for _ in range(3)]
    result: list[AtlasPoint] = []
    for index in range(count):
        angle = math.tau * index / count
        noise = 1 + 0.18 * math.sin(angle * 3 + phases[0]) + 0.1 * math.sin(angle * 7 + phases[1]) + 0.06 * math.sin(angle * 13 + phases[2]) + rng.uniform(-0.045, 0.045)
        result.append(AtlasPoint(x=cx + math.cos(angle) * rx * noise, y=cy + math.sin(angle) * ry * noise))
    return result


def _generated(atlas: StoryAtlas, name: str, kind: str, geometry_type: str, points: list[AtlasPoint], scope_id: str, layer: int, notes: str) -> AtlasCartographicFeature:
    return AtlasCartographicFeature(
        id=_unique_id(atlas, f"generated-{name}"),
        name=name,
        kind=kind,
        geometry_type=geometry_type,
        points=points,
        scope_id=scope_id,
        layer=layer,
        canon_status="suggested",
        confidence=0.5,
        source="generated-fantasy",
        notes=notes,
    )


def generate_fantasy_geography(slug: str, request: AtlasFantasyGenerateRequest) -> AtlasFantasyGenerateResponse:
    atlas = load_atlas(slug)
    locations = {item.id: item for item in atlas.locations}
    if request.scope_id and request.scope_id not in locations:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")
    rng = random.Random(request.seed)
    if request.replace_generated:
        atlas.features = [item for item in atlas.features if not (item.source == "generated-fantasy" and item.scope_id == request.scope_id)]
    center_x = locations[request.scope_id].x if request.scope_id else 0.0
    center_y = locations[request.scope_id].y if request.scope_id else 0.0
    added = 0
    for continent_index in range(request.continents):
        spread = 540 if request.continents > 1 else 0
        cx = center_x + (continent_index - (request.continents - 1) / 2) * spread + rng.uniform(-80, 80)
        cy = center_y + rng.uniform(-100, 100)
        rx = rng.uniform(280, 430) / max(1, math.sqrt(request.continents * 0.75))
        ry = rng.uniform(210, 340)
        atlas.features.append(_generated(atlas, f"Continent {continent_index + 1}", "continent", "polygon", _blob(rng, cx, cy, rx, ry, 48 + request.detail * 12), request.scope_id, -20, "Original seeded epic-fantasy landmass. Reshape and rename before promoting to canon."))
        added += 1
        for ridge_index in range(1 + request.detail // 2):
            angle = rng.uniform(-0.9, 0.9)
            length = rx * rng.uniform(0.7, 1.15)
            sx = cx - math.cos(angle) * length / 2 + rng.uniform(-rx * 0.15, rx * 0.15)
            sy = cy - math.sin(angle) * length / 2 + rng.uniform(-ry * 0.25, ry * 0.25)
            ridge = [AtlasPoint(x=sx + math.cos(angle) * length * step / 9 + rng.uniform(-18, 18), y=sy + math.sin(angle) * length * step / 9 + math.sin(step * 1.3) * 18 + rng.uniform(-12, 12)) for step in range(10)]
            atlas.features.append(_generated(atlas, f"Mountain Range {continent_index + 1}.{ridge_index + 1}", "mountains", "line", ridge, request.scope_id, -5, "Generated mountain spine."))
            added += 1
        for river_index in range(1 + request.detail):
            angle = rng.uniform(0, math.tau)
            sx, sy = cx + math.cos(angle) * rx * 0.15, cy + math.sin(angle) * ry * 0.15
            mouth_angle = angle + rng.uniform(-0.7, 0.7)
            mx, my = cx + math.cos(mouth_angle) * rx * 0.9, cy + math.sin(mouth_angle) * ry * 0.9
            river = [AtlasPoint(x=sx + (mx - sx) * step / 7 + math.sin(step * 1.8 + river_index) * 16, y=sy + (my - sy) * step / 7 + math.cos(step * 1.4 + river_index) * 12) for step in range(8)]
            atlas.features.append(_generated(atlas, f"River {continent_index + 1}.{river_index + 1}", "river", "line", river, request.scope_id, -4, "Generated drainage line."))
            added += 1
        for forest_index in range(max(1, request.detail - 1)):
            fx, fy = cx + rng.uniform(-rx * 0.5, rx * 0.5), cy + rng.uniform(-ry * 0.45, ry * 0.45)
            atlas.features.append(_generated(atlas, f"Forest {continent_index + 1}.{forest_index + 1}", "forest", "polygon", _blob(rng, fx, fy, rng.uniform(55, 110), rng.uniform(40, 90), 18), request.scope_id, -3, "Generated forest region."))
            added += 1
        road = [
            AtlasPoint(x=cx - rx * 0.58, y=cy + rng.uniform(-20, 20)),
            AtlasPoint(x=cx - rx * 0.18, y=cy - 30 + rng.uniform(-15, 15)),
            AtlasPoint(x=cx + rx * 0.2, y=cy + 20 + rng.uniform(-15, 15)),
            AtlasPoint(x=cx + rx * 0.58, y=cy - 15 + rng.uniform(-20, 20)),
        ]
        atlas.features.append(_generated(atlas, f"Old Road {continent_index + 1}", "road", "line", road, request.scope_id, 2, "Generated visual road only; it does not create a story route connection."))
        added += 1
    save_atlas(slug, atlas)
    return AtlasFantasyGenerateResponse(atlas=atlas, added_features=added, seed=request.seed)
