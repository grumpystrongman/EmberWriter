from pathlib import Path

from app import development, storage
from app.development_models import (
    CharacterArc,
    DevelopmentState,
    PlotBeat,
    RelationshipState,
    StoryThread,
)


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_story_development_round_trip_and_context(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Development Novel")["slug"]

    state = DevelopmentState(
        beats=[
            PlotBeat(
                id="beat-1",
                title="The bargain breaks",
                act="Act II",
                chapter=14,
                summary="Mara refuses the bargain and exposes the hidden cost.",
                purpose="Turn the alliance into open conflict.",
                characters=["Mara", "Elias"],
                thread_ids=["thread-bargain"],
            )
        ],
        character_arcs=[
            CharacterArc(
                character="Mara",
                want="Keep the city safe.",
                need="Trust other people with responsibility.",
                midpoint_shift="Learns control is creating the danger she fears.",
                climax_choice="Delegates power even though it risks betrayal.",
            )
        ],
        relationships=[
            RelationshipState(
                id="rel-mara-elias",
                participants=["Mara", "Elias"],
                label="fractured alliance",
                status="They still need each other but no longer trust the same plan.",
                trust=2,
                closeness=4,
                conflict=5,
                boundaries=["No more unilateral deals"],
                unresolved_tension=["Elias is hiding what the bargain cost him"],
            )
        ],
        threads=[
            StoryThread(
                id="thread-bargain",
                title="The hidden cost of the bargain",
                kind="setup_payoff",
                status="open",
                introduced_chapter=4,
                target_payoff_chapter=19,
                setup="The bargain saved the district but its price was concealed.",
                payoff="The price becomes the reason Mara must choose between control and trust.",
                participants=["Mara", "Elias"],
                beat_ids=["beat-1"],
            )
        ],
    )

    saved = development.save_development_state(slug, state)
    loaded = development.load_development_state(slug)

    assert saved.updated_at
    assert loaded.beats[0].title == "The bargain breaks"
    assert loaded.relationships[0].conflict == 5
    assert loaded.threads[0].target_payoff_chapter == 19

    context = development.build_development_context(slug)
    assert "Author-owned story development map" in context
    assert "The bargain breaks" in context
    assert "Mara / Elias" in context
    assert "hidden cost of the bargain" in context
    assert "climax=" in context


def test_generated_development_assigns_missing_ids() -> None:
    state = development.validate_generated_state(
        {
            "schema_version": 1,
            "beats": [{"id": "", "title": "Opening image"}],
            "character_arcs": [{"character": "Mara"}],
            "relationships": [
                {"id": "", "participants": ["Mara", "Elias"], "label": "allies"}
            ],
            "threads": [{"id": "", "title": "The missing key"}],
        }
    )

    assert state.beats[0].id.startswith("beat-")
    assert state.relationships[0].id.startswith("rel-")
    assert state.threads[0].id.startswith("thread-")


def test_empty_development_state_when_file_missing(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Empty Development")["slug"]

    state = development.load_development_state(slug)

    assert state.beats == []
    assert state.character_arcs == []
    assert state.relationships == []
    assert state.threads == []
