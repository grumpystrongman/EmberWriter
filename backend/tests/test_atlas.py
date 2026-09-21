from pathlib import Path

import pytest

from app import atlas, storage
from app.atlas_models import (
    AtlasAdviceRequest,
    AtlasBootstrapRequest,
    AtlasConnection,
    AtlasEvent,
    AtlasLocation,
    AtlasRouteCompareRequest,
    AtlasRouteRequest,
    StoryAtlas,
)
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def sample_atlas() -> StoryAtlas:
    return StoryAtlas(
        locations=[
            AtlasLocation(id="capital", name="Capital", x=0, y=0),
            AtlasLocation(id="ford", name="Old Ford", x=40, y=20),
            AtlasLocation(id="ridge", name="High Ridge", x=40, y=-40),
            AtlasLocation(id="temple", name="Ruined Temple", x=90, y=0),
        ],
        connections=[
            AtlasConnection(
                id="king-road",
                from_id="capital",
                to_id="temple",
                name="King's Road",
                distance=90,
                risk=1,
                drama=1,
                lore=1,
            ),
            AtlasConnection(
                id="ford-road",
                from_id="capital",
                to_id="ford",
                name="Floodplain Road",
                distance=45,
                risk=4,
                drama=5,
                lore=2,
            ),
            AtlasConnection(
                id="ford-temple",
                from_id="ford",
                to_id="temple",
                name="Old King Bridge",
                distance=50,
                risk=4,
                drama=5,
                lore=5,
            ),
            AtlasConnection(
                id="ridge-road",
                from_id="capital",
                to_id="ridge",
                name="Ridge Road",
                distance=55,
                risk=2,
                drama=2,
                lore=4,
                known_by=["Mira"],
            ),
            AtlasConnection(
                id="ridge-temple",
                from_id="ridge",
                to_id="temple",
                name="Monastery Track",
                distance=48,
                risk=2,
                drama=3,
                lore=5,
                known_by=["Mira"],
            ),
        ],
    )


def test_atlas_round_trip_and_validation(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Atlas Novel")["slug"]
    saved = atlas.save_atlas(slug, sample_atlas())
    loaded = atlas.load_atlas(slug)
    assert saved == loaded
    assert (storage.project_root(slug) / "world" / "atlas.json").exists()
    with pytest.raises(ValueError, match="unknown location"):
        StoryAtlas(
            locations=[AtlasLocation(id="a", name="A")],
            connections=[
                AtlasConnection(id="bad", from_id="a", to_id="missing", distance=2)
            ],
        )


def test_route_preferences_choose_different_story_paths() -> None:
    world = sample_atlas()
    fastest = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            mode="walk",
            preference="fastest",
        ),
    )
    dramatic = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            mode="walk",
            preference="dramatic",
        ),
    )
    assert [segment.connection_id for segment in fastest.segments] == ["king-road"]
    assert [segment.connection_id for segment in dramatic.segments] == [
        "ford-road",
        "ford-temple",
    ]
    assert dramatic.drama_score == 5
    assert fastest.total_distance == 90


def test_chapter_events_change_available_routes() -> None:
    world = sample_atlas()
    world.events = [
        AtlasEvent(
            id="bridge-falls",
            chapter=10,
            action="connection_close",
            target_id="king-road",
            summary="Bridge destroyed",
        ),
        AtlasEvent(
            id="bridge-restored",
            chapter=15,
            action="connection_open",
            target_id="king-road",
            summary="Bridge rebuilt",
        ),
    ]
    before = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            preference="fastest",
            chapter=9,
        ),
    )
    closed = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            preference="fastest",
            chapter=11,
        ),
    )
    restored = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            preference="fastest",
            chapter=16,
        ),
    )
    assert before.segments[0].connection_id == "king-road"
    assert closed.segments[0].connection_id == "ford-road"
    assert restored.segments[0].connection_id == "king-road"


def test_character_knowledge_can_unlock_private_route() -> None:
    world = sample_atlas()
    world.connections[0].active_until_chapter = 5
    world.connections[1].active_until_chapter = 5
    world.connections[2].active_until_chapter = 5
    with pytest.raises(ValueError, match="No walk route"):
        atlas.calculate_route(
            world,
            AtlasRouteRequest(
                origin_id="capital",
                destination_id="temple",
                chapter=10,
                character="Tamsin",
            ),
        )
    mira = atlas.calculate_route(
        world,
        AtlasRouteRequest(
            origin_id="capital",
            destination_id="temple",
            chapter=10,
            character="Mira",
            preference="lore",
        ),
    )
    assert [segment.connection_id for segment in mira.segments] == [
        "ridge-road",
        "ridge-temple",
    ]


def test_compare_routes_returns_all_preferences_even_when_paths_overlap() -> None:
    result = atlas.compare_routes(
        sample_atlas(),
        AtlasRouteCompareRequest(
            origin_id="capital", destination_id="temple", mode="horse"
        ),
    )
    assert len(result.routes) == 6
    assert result.unavailable_preferences == []
    assert {route.preference for route in result.routes} == {
        "fastest",
        "safest",
        "balanced",
        "dramatic",
        "lore",
        "relationship",
    }


def test_location_reveal_event_changes_character_route_knowledge() -> None:
    world = sample_atlas()
    secret = next(item for item in world.locations if item.id == "ridge")
    secret.known_by = ["Mira"]
    world.events.append(
        AtlasEvent(
            id="mira-shares-ridge",
            chapter=8,
            action="location_reveal",
            target_id="ridge",
            value="Tamsin",
            summary="Mira tells Tamsin about the old ridge route.",
        )
    )
    state_before = atlas.atlas_state(world, chapter=7, character="Tamsin")
    state_after = atlas.atlas_state(world, chapter=8, character="Tamsin")
    assert state_before["location_known"]["ridge"] is False
    assert state_before["connection_known"]["ridge-road"] is False
    assert state_after["location_known"]["ridge"] is True
    assert state_after["connection_known"]["ridge-road"] is False


def test_connection_knowledge_never_reveals_a_hidden_endpoint() -> None:
    world = sample_atlas()
    ridge = next(item for item in world.locations if item.id == "ridge")
    ridge.known_by = ["Mira"]
    ridge_road = next(item for item in world.connections if item.id == "ridge-road")
    ridge_road.known_by = []
    state = atlas.atlas_state(world, chapter=1, character="Tamsin")
    assert state["location_known"]["ridge"] is False
    assert state["connection_known"]["ridge-road"] is False


@pytest.mark.asyncio
async def test_bootstrap_uses_verified_sources_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Bootstrap Novel")["slug"]
    storage.save_text(
        slug, "world/greywater.md", "# Greywater\nA river crossing east of Blackwood."
    )

    async def fake_generate(*_args, **_kwargs) -> str:
        return '{"locations":[{"name":"Greywater","kind":"town","x":100,"y":20,"summary":"River crossing","source_paths":["world/greywater.md"]},{"name":"Blackwood","kind":"forest","x":0,"y":0},{"name":"Ghost Keep","kind":"ruin","x":220,"y":40,"source_paths":["world/greywater.md"]}],"connections":[{"name":"Forest Road","from":"Blackwood","to":"Greywater","distance":25,"risk":3,"drama":4,"lore":2,"relationship":2,"source_paths":["world/greywater.md"]}]}'

    monkeypatch.setattr(atlas, "generate", fake_generate)
    request = AtlasBootstrapRequest(provider=ProviderConfig(model="test"))
    result = await atlas.bootstrap_atlas(slug, request)
    assert result.added_locations == 3
    assert result.added_connections == 1
    greywater = next(item for item in result.atlas.locations if item.name == "Greywater")
    assert greywater.position_status == "inferred"
    assert greywater.canon_status == "canon"
    assert greywater.source_paths == ["world/greywater.md"]
    ghost = next(item for item in result.atlas.locations if item.name == "Ghost Keep")
    assert ghost.canon_status == "inferred"
    assert ghost.source_paths == []
    connection = result.atlas.connections[0]
    assert connection.canon_status == "inferred"
    assert connection.source_paths == ["world/greywater.md"]

    repeated = await atlas.bootstrap_atlas(slug, request)
    assert repeated.added_locations == 0
    assert repeated.added_connections == 0
    assert len(repeated.atlas.locations) == 3
    assert len(repeated.atlas.connections) == 1


@pytest.mark.asyncio
async def test_ai_advice_is_structured_and_never_mutates_atlas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Advice Novel")["slug"]
    atlas.save_atlas(slug, sample_atlas())

    async def fake_generate(*_args, **_kwargs) -> str:
        return '{"summary":"Use the Old King Bridge for the stronger reveal.","ideas":[{"title":"Bridge reveal","rationale":"It exposes enemy movement.","story_effect":"Adds pursuit pressure.","route_ids":["ford-temple"],"proposed_changes":["Place fresh bootprints near the bridge."]}],"continuity_warnings":["Do not reopen king-road before chapter 15."]}'

    monkeypatch.setattr(atlas, "generate", fake_generate)
    response = await atlas.advise_atlas(
        slug,
        AtlasAdviceRequest(
            prompt="Make the trip more dramatic",
            provider=ProviderConfig(model="test"),
            origin_id="capital",
            destination_id="temple",
            chapter=12,
        ),
    )
    assert response.ideas[0].route_ids == ["ford-temple"]
    assert "bootprints" in response.ideas[0].proposed_changes[0]
    assert atlas.load_atlas(slug) == sample_atlas()
