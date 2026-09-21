from pathlib import Path

import pytest

from app import atlas, atlas_hierarchy, storage
from app.atlas_models import AtlasBootstrapRequest, AtlasLocation, StoryAtlas
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def tag_value(location: AtlasLocation, prefix: str) -> str:
    return next((tag[len(prefix):] for tag in location.tags if tag.startswith(prefix)), "")


@pytest.mark.asyncio
async def test_spatial_hierarchy_builds_granular_parent_tree_with_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Granular Atlas Novel")["slug"]
    storage.save_text(
        slug,
        "world/kaelens-home.md",
        "# Rowan's Home\n"
        "Rowan's Bedroom is upstairs in Rowan's Home. "
        "The Kitchen opens toward the Garden.\n",
    )

    async def fake_generate(*_args, **_kwargs) -> str:
        return """{
          "locations": [
            {"name":"Rowan's Home","kind":"house","scale":"building","parent":"","x":0,"y":0,"summary":"Home base","canon_status":"canon","confidence":0.96,"source_paths":["world/kaelens-home.md"]},
            {"name":"Upper Floor","kind":"floor","scale":"floor","parent":"Rowan's Home","x":0,"y":-40,"summary":"Upper level","canon_status":"inferred","confidence":0.72,"inference_reason":"The bedroom is explicitly upstairs."},
            {"name":"Rowan's Bedroom","kind":"bedroom","scale":"room","parent":"Upper Floor","x":-40,"y":0,"summary":"Rowan's room","canon_status":"canon","confidence":0.95,"source_paths":["world/kaelens-home.md"]},
            {"name":"Kitchen","kind":"kitchen","scale":"room","parent":"Rowan's Home","x":35,"y":30,"summary":"Kitchen","canon_status":"canon","confidence":0.94,"source_paths":["world/kaelens-home.md"]},
            {"name":"Garden","kind":"garden","scale":"area","parent":"Rowan's Home","x":90,"y":30,"summary":"Garden","canon_status":"canon","confidence":0.93,"source_paths":["world/kaelens-home.md"]},
            {"name":"Possible Cellar","kind":"cellar","scale":"room","parent":"Rowan's Home","x":0,"y":70,"summary":"Optional author idea","canon_status":"suggested","confidence":0.4,"inference_reason":"A cellar could fit the house, but the manuscript does not establish one."}
          ],
          "connections": []
        }"""

    monkeypatch.setattr(atlas_hierarchy, "generate", fake_generate)
    result = await atlas_hierarchy.build_spatial_hierarchy(
        slug, AtlasBootstrapRequest(provider=ProviderConfig(model="test"))
    )

    by_name = {item.name: item for item in result.atlas.locations}
    home = by_name["Rowan's Home"]
    upper = by_name["Upper Floor"]
    bedroom = by_name["Rowan's Bedroom"]
    kitchen = by_name["Kitchen"]
    garden = by_name["Garden"]
    cellar = by_name["Possible Cellar"]

    assert tag_value(home, "scale:") == "building"
    assert tag_value(home, "origin:") == "manuscript"
    assert home.canon_status == "canon"
    assert tag_value(upper, "parent:") == home.id
    assert tag_value(upper, "scale:") == "floor"
    assert tag_value(upper, "origin:") == "ai-inference"
    assert "upstairs" in tag_value(upper, "basis:")
    assert upper.canon_status == "inferred"
    assert tag_value(bedroom, "parent:") == upper.id
    assert tag_value(bedroom, "scale:") == "room"
    assert bedroom.source_paths == ["world/kaelens-home.md"]
    assert tag_value(kitchen, "parent:") == home.id
    assert tag_value(garden, "scale:") == "area"
    assert cellar.canon_status == "suggested"
    assert tag_value(cellar, "origin:") == "ai-suggestion"
    assert cellar.source_paths == []

    repeated = await atlas_hierarchy.build_spatial_hierarchy(
        slug, AtlasBootstrapRequest(provider=ProviderConfig(model="test"))
    )
    assert repeated.added_locations == 0
    assert len(repeated.atlas.locations) == 6


@pytest.mark.asyncio
async def test_spatial_hierarchy_preserves_author_canon_and_adds_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Author Atlas Novel")["slug"]
    atlas.save_atlas(
        slug,
        StoryAtlas(
            locations=[
                AtlasLocation(
                    id="black-lantern",
                    name="Black Lantern Inn",
                    kind="building",
                    tags=["scale:building", "origin:author"],
                    canon_status="canon",
                    position_status="canon",
                    confidence=1.0,
                )
            ]
        ),
    )

    async def fake_generate(*_args, **_kwargs) -> str:
        return """{
          "locations": [
            {"name":"Black Lantern Inn","kind":"inn","scale":"building","parent":"","x":0,"y":0,"canon_status":"inferred","confidence":0.6},
            {"name":"Taproom","kind":"room","scale":"room","parent":"Black Lantern Inn","x":0,"y":0,"canon_status":"inferred","confidence":0.7,"inference_reason":"Scenes explicitly take place in the inn's taproom."}
          ],
          "connections": []
        }"""

    monkeypatch.setattr(atlas_hierarchy, "generate", fake_generate)
    result = await atlas_hierarchy.build_spatial_hierarchy(
        slug, AtlasBootstrapRequest(provider=ProviderConfig(model="test"))
    )

    by_name = {item.name: item for item in result.atlas.locations}
    inn = by_name["Black Lantern Inn"]
    taproom = by_name["Taproom"]
    assert inn.canon_status == "canon"
    assert tag_value(inn, "origin:") == "author"
    assert inn.position_status == "canon"
    assert tag_value(taproom, "parent:") == inn.id
    assert tag_value(taproom, "scale:") == "room"
    assert taproom.canon_status == "inferred"
