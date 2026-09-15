from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .atlas import load_atlas, save_atlas
from .atlas_cartography import import_geojson
from .atlas_models import AtlasGeoJsonImportRequest, StoryAtlas
from .storage import project_root, slugify

HISTORICAL_SOURCES_PATH = Path("world") / "historical_sources.json"
_USER_AGENT = "EmberWriter/0.14 (+https://github.com/grumpystrongman/EmberWriter)"
_YEAR_RE = re.compile(r"(?<!\d)(1\d{3}|20\d{2}|2100)\s*$")


class HistoricalSource(BaseModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    provider: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(default="reference", max_length=80)
    url: str = Field(default="", max_length=4000)
    thumbnail_url: str = Field(default="", max_length=4000)
    date_label: str = Field(default="", max_length=200)
    year_start: int | None = Field(default=None, ge=1000, le=2100)
    year_end: int | None = Field(default=None, ge=1000, le=2100)
    relevance: float = Field(default=0.5, ge=0, le=1)
    rights: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)


class HistoricalPlaceRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    scope_id: str = Field(default="", max_length=120)
    radius_km: float = Field(default=4.0, ge=0.25, le=50)
    year_window: int = Field(default=30, ge=1, le=200)
    max_modern_features: int = Field(default=600, ge=25, le=2000)
    max_sources: int = Field(default=24, ge=1, le=100)
    include_modern_context: bool = True


class HistoricalPlaceResponse(BaseModel):
    atlas: StoryAtlas
    query: str
    resolved_place: str
    year: int
    latitude: float
    longitude: float
    added_features: int = 0
    added_sources: int = 0
    sources: list[HistoricalSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _sources_file(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root / HISTORICAL_SOURCES_PATH


def load_historical_sources(slug: str) -> list[HistoricalSource]:
    path = _sources_file(slug)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = payload.get("sources", []) if isinstance(payload, dict) else []
    result: list[HistoricalSource] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            result.append(HistoricalSource.model_validate(item))
        except (TypeError, ValueError):
            continue
    return result


def _save_historical_sources(slug: str, sources: list[HistoricalSource]) -> None:
    path = _sources_file(slug)
    existing = {item.id: item for item in load_historical_sources(slug)}
    for source in sources:
        existing[source.id] = source
    ordered = sorted(existing.values(), key=lambda item: (-item.relevance, item.provider, item.title))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(
            {"schema_version": 1, "sources": [item.model_dump(mode="json") for item in ordered]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temp.replace(path)


def parse_historical_place_query(query: str) -> tuple[str, int]:
    cleaned = query.strip()
    match = _YEAR_RE.search(cleaned)
    if match is None:
        raise ValueError("Historical place queries must end with a year, for example: New Harmony, Indiana, 1820")
    year = int(match.group(1))
    place = cleaned[: match.start()].rstrip(" ,-")
    if len(place) < 2:
        raise ValueError("Historical place query is missing a place name")
    return place, year


def _source_id(provider: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{provider}|{url}|{title}".encode()).hexdigest()[:10]
    return f"{slugify(provider)[:32]}-{slugify(title)[:66]}-{digest}"[:120]


def _bounds(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / max(10.0, 111.0 * math.cos(math.radians(lat)))
    return lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta


def _year_from(value: Any) -> int | None:
    match = re.search(r"(?<!\d)(1\d{3}|20\d{2}|2100)(?!\d)", str(value or ""))
    return int(match.group(1)) if match else None


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item is not None)
    return str(value or "")


async def _geocode_place(client: httpx.AsyncClient, place: str) -> dict[str, Any]:
    response = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 1},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Could not resolve historical place: {place}")
    item = payload[0]
    return {
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
        "display_name": str(item.get("display_name") or place),
        "country_code": str((item.get("address") or {}).get("country_code") or "").lower(),
    }


def _osm_feature_kind(tags: dict[str, Any]) -> tuple[str, int]:
    if tags.get("historic"):
        return "historic", 0
    if tags.get("waterway"):
        return "waterway", 0
    if tags.get("natural") in {"water", "wood", "wetland", "scrub", "heath"}:
        return "natural", 0
    if tags.get("highway"):
        return "road", 1
    if tags.get("building"):
        return "building", 2
    return "context", 3


def _osm_to_geojson(payload: dict[str, Any], max_features: int) -> dict[str, Any]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for element in payload.get("elements", []) if isinstance(payload, dict) else []:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
        kind, priority = _osm_feature_kind(tags)
        geometry: dict[str, Any] | None = None
        if element.get("type") == "node" and "lat" in element and "lon" in element:
            geometry = {"type": "Point", "coordinates": [element["lon"], element["lat"]]}
        else:
            raw_geometry = element.get("geometry")
            if isinstance(raw_geometry, list):
                coordinates = [
                    [item.get("lon"), item.get("lat")]
                    for item in raw_geometry
                    if isinstance(item, dict) and item.get("lon") is not None and item.get("lat") is not None
                ]
                if len(coordinates) >= 2:
                    closed = len(coordinates) >= 4 and coordinates[0] == coordinates[-1]
                    polygonish = bool(tags.get("building")) or tags.get("natural") in {
                        "water",
                        "wood",
                        "wetland",
                        "scrub",
                        "heath",
                    }
                    geometry = {
                        "type": "Polygon" if closed and polygonish else "LineString",
                        "coordinates": [coordinates] if closed and polygonish else coordinates,
                    }
        if geometry is None:
            continue
        properties = {
            str(key): value
            for key, value in tags.items()
            if isinstance(value, (str, int, float, bool))
        }
        properties["name"] = str(tags.get("name") or f"OSM {kind} {element.get('id', '')}")
        properties["osm_type"] = str(element.get("type") or "")
        properties["osm_id"] = int(element.get("id") or 0)
        candidates.append(
            (
                priority,
                {"type": "Feature", "properties": properties, "geometry": geometry},
            )
        )
    candidates.sort(key=lambda item: item[0])
    return {
        "type": "FeatureCollection",
        "features": [item[1] for item in candidates[:max_features]],
    }


async def _fetch_osm_geojson(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    radius_km: float,
    max_features: int,
) -> dict[str, Any]:
    south, west, north, east = _bounds(lat, lon, radius_km)
    bbox = f"{south:.7f},{west:.7f},{north:.7f},{east:.7f}"
    query = f"""[out:json][timeout:25];
(
  node[\"historic\"]({bbox});
  way[\"historic\"]({bbox});
  way[\"waterway\"]({bbox});
  way[\"natural\"~\"water|wood|wetland|scrub|heath\"]({bbox});
  way[\"highway\"]({bbox});
  way[\"building\"]({bbox});
);
out tags geom qt;"""
    response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query})
    response.raise_for_status()
    return _osm_to_geojson(response.json(), max_features)


async def _fetch_loc_sources(
    client: httpx.AsyncClient,
    place: str,
    year: int,
    window: int,
    limit: int,
) -> list[HistoricalSource]:
    response = await client.get(
        "https://www.loc.gov/maps/",
        params={
            "q": place,
            "dates": f"{max(1000, year - window)}/{min(2100, year + window)}",
            "fo": "json",
            "at": "results",
            "c": min(100, max(5, limit)),
        },
    )
    response.raise_for_status()
    payload = response.json()
    raw_results = payload.get("results", []) if isinstance(payload, dict) else []
    sources: list[HistoricalSource] = []
    tokens = {token for token in re.split(r"\W+", place.casefold()) if len(token) > 2}
    for item in raw_results if isinstance(raw_results, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Library of Congress map")
        date_label = _text(item.get("date") or item.get("dates"))
        item_year = _year_from(date_label)
        closeness = 0.45 if item_year is None else max(0.0, 1 - abs(item_year - year) / max(1, window * 2))
        title_tokens = {token for token in re.split(r"\W+", title.casefold()) if token}
        place_overlap = len(tokens & title_tokens) / max(1, len(tokens))
        relevance = min(1.0, 0.35 + closeness * 0.4 + place_overlap * 0.25)
        url = str(item.get("id") or item.get("url") or "")
        image_urls = item.get("image_url")
        thumbnail = str(image_urls[0]) if isinstance(image_urls, list) and image_urls else ""
        rights = _text(item.get("rights") or item.get("rights_information"))
        sources.append(
            HistoricalSource(
                id=_source_id("loc", title, url),
                provider="Library of Congress",
                title=title,
                source_type="historical-map",
                url=url,
                thumbnail_url=thumbnail,
                date_label=date_label,
                year_start=item_year,
                year_end=item_year,
                relevance=relevance,
                rights=rights,
                notes=f"Map catalog result found for {place}, centered on requested year {year}.",
            )
        )
    return sorted(sources, key=lambda item: -item.relevance)[:limit]


async def _fetch_usgs_sources(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    radius_km: float,
    year: int,
    window: int,
    limit: int,
) -> list[HistoricalSource]:
    south, west, north, east = _bounds(lat, lon, radius_km)
    response = await client.get(
        "https://tnmaccess.nationalmap.gov/api/v1/products",
        params={
            "datasets": "Historical Topographic Maps",
            "bbox": f"{west:.7f},{south:.7f},{east:.7f},{north:.7f}",
            "max": min(100, max(10, limit * 3)),
            "outputFormat": "JSON",
        },
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    sources: list[HistoricalSource] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("productTitle") or "USGS historical topo")
        date_label = _text(
            item.get("sourceDate")
            or item.get("publicationDate")
            or item.get("dateCreated")
            or item.get("lastUpdated")
        )
        item_year = _year_from(date_label) or _year_from(title)
        if item_year is not None and abs(item_year - year) > max(window * 2, 40):
            continue
        closeness = 0.35 if item_year is None else max(0.0, 1 - abs(item_year - year) / max(1, window * 2))
        url = str(item.get("downloadURL") or item.get("url") or item.get("metaUrl") or "")
        sources.append(
            HistoricalSource(
                id=_source_id("usgs", title, url),
                provider="USGS The National Map",
                title=title,
                source_type="historical-topographic-map",
                url=url,
                date_label=date_label,
                year_start=item_year,
                year_end=item_year,
                relevance=min(1.0, 0.45 + closeness * 0.5),
                rights="U.S. Geological Survey public data; review product metadata for details.",
                notes=f"Historical topo product intersecting the requested {radius_km:g} km area.",
            )
        )
    return sorted(sources, key=lambda item: -item.relevance)[:limit]


async def assemble_historical_place(
    slug: str,
    request: HistoricalPlaceRequest,
) -> HistoricalPlaceResponse:
    place, year = parse_historical_place_query(request.query)
    atlas = load_atlas(slug)
    if request.scope_id and request.scope_id not in {item.id for item in atlas.locations}:
        raise ValueError(f"Unknown atlas scope: {request.scope_id}")

    warnings: list[str] = []
    sources: list[HistoricalSource] = []
    added_features = 0
    timeout = httpx.Timeout(45.0, connect=15.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    ) as client:
        resolved = await _geocode_place(client, place)
        lat, lon = resolved["lat"], resolved["lon"]
        resolved_place = resolved["display_name"]

        if request.include_modern_context:
            try:
                geojson = await _fetch_osm_geojson(
                    client,
                    lat,
                    lon,
                    request.radius_km,
                    request.max_modern_features,
                )
                if geojson.get("features"):
                    atlas.features = [
                        feature
                        for feature in atlas.features
                        if not (
                            feature.scope_id == request.scope_id
                            and feature.source == "openstreetmap-current"
                            and feature.properties.get("requested_year") == year
                        )
                    ]
                    atlas = save_atlas(slug, atlas)
                    before_ids = {item.id for item in atlas.features}
                    source_name = f"OpenStreetMap current reference — {resolved_place}"
                    imported = import_geojson(
                        slug,
                        AtlasGeoJsonImportRequest(
                            geojson=geojson,
                            scope_id=request.scope_id,
                            source_name=source_name,
                            replace_imported=False,
                        ),
                    )
                    atlas = imported.atlas
                    for feature in atlas.features:
                        if feature.id in before_ids:
                            continue
                        feature.source = "openstreetmap-current"
                        feature.notes = (
                            f"Current OpenStreetMap reference assembled for a story set in {year}. "
                            "This is spatial context, not evidence that the feature existed in the requested year."
                        )
                        feature.properties["requested_year"] = year
                        feature.properties["historical_status"] = "modern-reference"
                    atlas = save_atlas(slug, atlas)
                    added_features = imported.added_features
                osm_url = f"https://www.openstreetmap.org/#map=14/{lat:.6f}/{lon:.6f}"
                sources.append(
                    HistoricalSource(
                        id=_source_id("osm", resolved_place, osm_url),
                        provider="OpenStreetMap",
                        title=f"Current base geography for {resolved_place}",
                        source_type="modern-gis-reference",
                        url=osm_url,
                        date_label="present-day",
                        relevance=0.72,
                        rights="OpenStreetMap data © OpenStreetMap contributors, ODbL.",
                        notes=(
                            f"Current roads, buildings, waterways, natural features and historic-tagged objects "
                            f"within {request.radius_km:g} km. Use as a reference layer for {year}, not historical proof."
                        ),
                    )
                )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                warnings.append(f"OpenStreetMap context could not be assembled: {exc}")

        try:
            sources.extend(
                await _fetch_loc_sources(
                    client,
                    place,
                    year,
                    request.year_window,
                    request.max_sources,
                )
            )
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            warnings.append(f"Library of Congress map search failed: {exc}")

        if resolved.get("country_code") == "us":
            if year < 1884:
                warnings.append(
                    "USGS historical topographic maps begin in 1884, so no USGS topo layer was requested for this year."
                )
            else:
                try:
                    sources.extend(
                        await _fetch_usgs_sources(
                            client,
                            lat,
                            lon,
                            request.radius_km,
                            year,
                            request.year_window,
                            request.max_sources,
                        )
                    )
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    warnings.append(f"USGS historical topo search failed: {exc}")

    deduped: dict[str, HistoricalSource] = {}
    for source in sources:
        existing = deduped.get(source.id)
        if existing is None or source.relevance > existing.relevance:
            deduped[source.id] = source
    ranked = sorted(deduped.values(), key=lambda item: -item.relevance)
    ranked = ranked[: request.max_sources + 1]
    _save_historical_sources(slug, ranked)

    return HistoricalPlaceResponse(
        atlas=atlas,
        query=request.query,
        resolved_place=resolved_place,
        year=year,
        latitude=lat,
        longitude=lon,
        added_features=added_features,
        added_sources=len(ranked),
        sources=ranked,
        warnings=warnings,
    )
