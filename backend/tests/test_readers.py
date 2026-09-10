import asyncio
from pathlib import Path

from app import binder, readers, storage
from app.models import ProviderConfig
from app.reader_models import ReaderRunCreate


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_reader_walks_binder_order_and_synthesizes(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Reader Book")
    slug = project["slug"]
    state = binder.get_binder(slug)
    draft = next(node for node in state.nodes if node.title == "Draft")
    first = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")
    storage.save_text(slug, first.path or "", "# First\n\nMara opened the sealed door and found ash.\n")
    before = {node.id for node in state.nodes}
    state = binder.create_node(
        slug,
        binder.BinderNodeCreate(title="Second", kind="document", parent_id=draft.id),
    )
    second = next(node for node in state.nodes if node.id not in before)
    assert second.path
    storage.save_text(slug, second.path, "# Second\n\nMara learned the ash spelled her name.\n")

    responses = iter(
        [
            '{"reaction":"Hooked by the sealed door.","engagement":8,"pacing":8,"clarity":9,"emotional_impact":7,"favorite_moment":"the ash","confusion":[],"predictions":["The ash is a warning"],"character_reactions":["Mara feels reckless"],"keep_reading":"yes","craft_notes":[]}',
            '{"reaction":"The reveal pays off the ash image.","engagement":9,"pacing":8,"clarity":9,"emotional_impact":9,"favorite_moment":"her name","confusion":[],"predictions":["Someone knows Mara"],"character_reactions":["Mara is frightened"],"keep_reading":"absolutely","craft_notes":[]}',
            '{"overall_reaction":"A strong compact mystery arc.","score":9,"audience_fit":"mystery readers","genre_fit":"strong","strongest_elements":["payoff"],"weakest_elements":[],"character_feedback":["Mara is compelling"],"pacing_feedback":["fast"],"plot_feedback":["clear causality"],"voice_feedback":["clean"],"ending_feedback":["satisfying"],"unresolved_confusion":[],"fulfilled_predictions":["ash mattered"],"broken_promises":[],"top_revisions":["expand aftermath"],"would_recommend":"yes"}',
        ]
    )

    async def fake_generate(*args, **kwargs) -> str:
        return next(responses)

    monkeypatch.setattr(readers, "generate", fake_generate)
    run = readers.create_reader_run(
        slug,
        ReaderRunCreate(persona="fan", genre="Gothic mystery", focus="Track the mystery hook"),
    )
    assert run["total_documents"] == 2
    assert run["status"] == "reading"

    provider = ProviderConfig(model="test")
    first_step = asyncio.run(readers.step_reader_run(slug, run["id"], provider))
    assert first_step["action"] == "chapter_read"
    assert first_step["chapter_note"]["chapter_title"] == first.title
    assert first_step["run"]["current_index"] == 1

    second_step = asyncio.run(readers.step_reader_run(slug, run["id"], provider))
    assert second_step["run"]["status"] == "ready_to_synthesize"
    assert second_step["chapter_note"]["chapter_title"] == second.title

    final_step = asyncio.run(readers.step_reader_run(slug, run["id"], provider))
    assert final_step["action"] == "synthesized"
    assert final_step["run"]["status"] == "completed"
    assert final_step["run"]["verdict"]["score"] == 9
    assert readers.list_reader_runs(slug)[0]["score"] == 9


def test_reader_notes_become_stale_when_source_changes(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Reader Stale")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    storage.save_text(slug, path, "# One\n\nThe room was empty.\n")

    async def fake_generate(*args, **kwargs) -> str:
        return '{"reaction":"Clear.","engagement":5,"pacing":5,"clarity":9,"emotional_impact":4,"favorite_moment":"","confusion":[],"predictions":[],"character_reactions":[],"keep_reading":"yes","craft_notes":[]}'

    monkeypatch.setattr(readers, "generate", fake_generate)
    run = readers.create_reader_run(slug, ReaderRunCreate(persona="casual_reader", genre="Thriller"))
    asyncio.run(readers.step_reader_run(slug, run["id"], ProviderConfig(model="test")))
    assert readers.get_reader_run(slug, run["id"])["stale_documents"] == 0

    storage.save_text(slug, path, "# One\n\nThe room held a body.\n")
    reopened = readers.get_reader_run(slug, run["id"])
    assert reopened["stale_documents"] == 1
    assert reopened["notes"][0]["stale"] is True


def test_reader_personas_are_distinct() -> None:
    catalog = readers.persona_catalog()
    assert {item["id"] for item in catalog} == {"fan", "casual_reader", "strong_editor"}
    assert len({item["description"] for item in catalog}) == 3
