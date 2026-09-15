from pathlib import Path
from typing import Any

import pytest

from app import atlas, atlas_historical, storage
from app.atlas_historical import HistoricalPlaceRequest, HistoricalSource
from app.atlas_models import AtlasLocation, StoryAtlas


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_parse_historical_place_query() -> None:
    place, year = atlas_historical.parse_historical_place_query("New Harmony, Indiana, 1820")
    assert place == "New Harmony, Indiana"
    assert year == 1820
    with pytest.raises(ValueError, match="must end with a year"):
        atlas_historical.parse_historical_place_query("New Harmony, Indiana")


@pytest.mark.asyncio
async def test_historical_assembler_imports_reference_gis_and_persists_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Historical New Harmony")["slug"]
    atlas.save_atlas(
        slug,
        StoryAtlas(locations=[AtlasLocation(id="town", name="New Harmony", x=100, y=200)]),
    )

    async def fake_geocode(client: object, place: str) -> dict[str, Any]:
        assert place == "New Harmony, Indiana"
        return {
            "lat": 38.1298,
            "lon": -87.9350,
            "display_name": "New Harmony, Posey County, Indiana, United States",
            "country_code": "us",
        }

    async def fake_osm(
        client: object,
        lat: float,
        lon: float,
        radius_km: float,
        max_features: int,
    ) -> dict[str, Any]:
        assert radius_km == 4
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Wabash River", "waterway": "river"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-87.95, 38.12], [-87.94, 38.13], [-87.93, 38.14]],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"name": "Current Main Street", "highway": "primary"},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-87.94, 38.125], [-87.93, 38.135]],
                    },
                },
            ],
        }

    async def fake_loc(
        client: object,
        place: str,
        year: int,
        window: int,
        limit: int,
    ) -> list[HistoricalSource]:
        return [
            HistoricalSource(
                id="loc-new-harmony-1820",
                provider="Library of Congress",
                title="Map of Indiana and adjacent country",
                source_type="historical-map",
                url="https://www.loc.gov/item/example/",
                date_label="1820",
                year_start=1820,
                year_end=1820,
                relevance=0.95,
            )
        ]

    monkeypatch.setattr(atlas_historical, "_geocode_place", fake_geocode)
    monkeypatch.setattr(atlas_historical, "_fetch_osm_geojson", fake_osm)
    monkeypatch.setattr(atlas_historical, "_fetch_loc_sources", fake_loc)

    result = await atlas_historical.assemble_historical_place(
        slug,
        HistoricalPlaceRequest(query="New Harmony, Indiana, 1820", scope_id="town"),
    )

    assert result.year == 1820
    assert result.added_features == 2
    assert result.added_sources == 2
    assert any("USGS historical topographic maps begin in 1884" in item for item in result.warnings)
    imported = [item for item in result.atlas.features if item.scope_id == "town"]
    assert len(imported) == 2
    assert all(item.source == "openstreetmap-current" for item in imported)
    assert all(item.canon_status == "inferred" for item in imported)
    assert all(item.properties["requested_year"] == 1820 for item in imported)
    assert all(item.properties["historical_status"] == "modern-reference" for item in imported)

    persisted = atlas_historical.load_historical_sources(slug)
    assert {item.provider for item in persisted} == {"OpenStreetMap", "Library of Congress"}
    assert any(item.year_start == 1820 for item in persisted)
