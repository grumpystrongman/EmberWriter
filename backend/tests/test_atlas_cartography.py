from pathlib import Path

import pytest

from app import atlas, atlas_cartography, storage
from app.atlas_models import (
    AtlasFantasyGenerateRequest,
    AtlasGeographySuggestRequest,
    AtlasGeoJsonImportRequest,
    AtlasLocation,
    StoryAtlas,
)
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_generated_fantasy_cartography_is_seeded_and_persisted(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Fantasy Atlas")["slug"]
    atlas.save_atlas(slug, StoryAtlas(locations=[AtlasLocation(id="realm", name="Realm", x=120, y=-40)]))

    first = atlas_cartography.generate_fantasy_geography(
        slug,
        AtlasFantasyGenerateRequest(scope_id="realm", seed=1234, continents=2, detail=3),
    )
    assert first.added_features > 6
    assert first.atlas.features
    assert all(item.scope_id == "realm" for item in first.atlas.features)
    assert all(item.canon_status == "suggested" for item in first.atlas.features)
    snapshot = [(item.kind, [(point.x, point.y) for point in item.points]) for item in first.atlas.features]

    second = atlas_cartography.generate_fantasy_geography(
        slug,
        AtlasFantasyGenerateRequest(scope_id="realm", seed=1234, continents=2, detail=3),
    )
    assert snapshot == [(item.kind, [(point.x, point.y) for point in item.points]) for item in second.atlas.features]
    assert atlas.load_atlas(slug).features == second.atlas.features


def test_geojson_import_projects_real_geography_into_story_scope(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Historical Atlas")["slug"]
    atlas.save_atlas(slug, StoryAtlas(locations=[AtlasLocation(id="town", name="Town", x=500, y=600)]))
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "River Road", "highway": "primary"},
                "geometry": {"type": "LineString", "coordinates": [[-88.0, 38.0], [-87.99, 38.01], [-87.98, 38.015]]},
            },
            {
                "type": "Feature",
                "properties": {"name": "Wabash", "waterway": "river"},
                "geometry": {"type": "LineString", "coordinates": [[-88.02, 38.0], [-88.015, 38.02]]},
            },
        ],
    }
    result = atlas_cartography.import_geojson(
        slug,
        AtlasGeoJsonImportRequest(geojson=payload, scope_id="town", source_name="Test GIS"),
    )
    assert result.added_features == 2
    assert {item.kind for item in result.atlas.features} == {"road", "river"}
    assert all(item.source == "geojson" for item in result.atlas.features)
    assert all(item.source_crs == "EPSG:4326" for item in result.atlas.features)
    assert all(item.canon_status == "inferred" for item in result.atlas.features)
    xs = [point.x for item in result.atlas.features for point in item.points]
    ys = [point.y for item in result.atlas.features for point in item.points]
    assert min(xs) < 500 < max(xs)
    assert min(ys) < 600 < max(ys)


@pytest.mark.asyncio
async def test_manuscript_ai_suggestions_remain_suggested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Manuscript Atlas")["slug"]
    root = storage.project_root(slug)
    (root / "draft").mkdir(parents=True, exist_ok=True)
    (root / "draft" / "chapter-1.md").write_text(
        "Mara crossed the Stonebridge over the Grey River, then followed the eastern road into Blackwood.",
        encoding="utf-8",
    )
    atlas.save_atlas(
        slug,
        StoryAtlas(
            locations=[
                AtlasLocation(id="stonebridge", name="Stonebridge", x=0, y=0),
                AtlasLocation(id="blackwood", name="Blackwood", x=220, y=-20),
            ]
        ),
    )

    async def fake_generate(*args: object, **kwargs: object) -> str:
        return """{
          "features": [
            {"name":"Grey River","kind":"river","geometry_type":"line","points":[[-80,-20],[0,0],[90,25]],"source_paths":["draft/chapter-1.md"],"notes":"The manuscript explicitly says Stonebridge crosses the Grey River."},
            {"name":"Eastern Road","kind":"road","geometry_type":"line","points":[[0,0],[100,-10],[220,-20]],"source_paths":["draft/chapter-1.md"],"notes":"The manuscript explicitly describes the eastward road toward Blackwood."}
          ],
          "warnings": []
        }"""

    monkeypatch.setattr(atlas_cartography, "generate", fake_generate)
    result = await atlas_cartography.suggest_geography(
        slug,
        AtlasGeographySuggestRequest(provider=ProviderConfig(model="test"), max_features=20),
    )
    assert result.added_features == 2
    assert {item.name for item in result.atlas.features} == {"Grey River", "Eastern Road"}
    assert all(item.canon_status == "suggested" for item in result.atlas.features)
    assert all(item.source == "manuscript-ai" for item in result.atlas.features)
    assert all("draft/chapter-1.md" in item.source_paths for item in result.atlas.features)
