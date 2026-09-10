import json
from pathlib import Path

import pytest

from app import binder, storage
from app.binder_models import (
    BinderCollectionCreate,
    BinderNodeCreate,
    BinderNodeUpdate,
    BinderReorderRequest,
)


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def node_by_title(state, title: str):
    return next(node for node in state.nodes if node.title == title)


def children(state, parent_id: str):
    return sorted(
        (node for node in state.nodes if node.parent_id == parent_id),
        key=lambda node: node.position,
    )


def test_binder_seeds_existing_project_with_stable_ids(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Test")
    slug = project["slug"]

    first = binder.get_binder(slug)
    second = binder.get_binder(slug)
    draft = node_by_title(first, "Draft")
    chapter = next(node for node in first.nodes if node.path == "manuscript/chapter-001.md")

    assert [node_by_title(first, title).id for title in binder.ROOT_TITLES] == [
        node_by_title(second, title).id for title in binder.ROOT_TITLES
    ]
    assert chapter.parent_id == draft.id
    assert chapter.id == next(
        node.id for node in second.nodes if node.path == "manuscript/chapter-001.md"
    )
    assert storage.read_text(slug, binder.BINDER_PATH)


def test_create_update_and_reorder_preserve_file_paths(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Reorder")
    slug = project["slug"]
    state = binder.get_binder(slug)
    draft = node_by_title(state, "Draft")

    state = binder.create_node(
        slug,
        BinderNodeCreate(title="Second Scene", kind="document", parent_id=draft.id),
    )
    second = node_by_title(state, "Second Scene")
    assert second.path == "manuscript/second-scene.md"
    assert storage.read_text(slug, second.path).startswith("# Second Scene")

    state = binder.update_node(
        slug,
        second.id,
        BinderNodeUpdate(
            synopsis="A confrontation changes the alliance.",
            label="Turning Point",
            status="First Draft",
            keywords=["alliance", "betrayal"],
            target_words=1800,
            custom_metadata={"pov": "Mara", "location": "North Gate"},
        ),
    )
    second = next(node for node in state.nodes if node.id == second.id)
    assert second.synopsis.startswith("A confrontation")
    assert second.custom_metadata["pov"] == "Mara"

    before_paths = {node.id: node.path for node in children(state, draft.id)}
    ordered = children(state, draft.id)
    state = binder.reorder_nodes(
        slug,
        BinderReorderRequest(
            parent_id=draft.id,
            node_ids=list(reversed([node.id for node in ordered])),
        ),
    )
    after = children(state, draft.id)

    assert [node.id for node in after] == list(reversed([node.id for node in ordered]))
    assert {node.id: node.path for node in after} == before_paths


def test_sync_adds_external_files_without_removing_missing_nodes(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Sync")
    slug = project["slug"]
    state = binder.get_binder(slug)
    chapter = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")

    storage.save_text(slug, "manuscript/external-scene.md", "# External Scene\n\nNew prose here.")
    (storage.project_root(slug) / "manuscript" / "chapter-001.md").unlink()

    synced = binder.sync_binder(slug)
    external = next(node for node in synced.nodes if node.path == "manuscript/external-scene.md")
    missing = next(node for node in synced.nodes if node.id == chapter.id)
    durable = json.loads(storage.read_text(slug, binder.BINDER_PATH))
    durable_missing = next(node for node in durable["nodes"] if node["id"] == chapter.id)

    assert external.title == "External Scene"
    assert missing.custom_metadata["source_missing"] is True
    assert missing.id == chapter.id
    assert "source_missing" not in durable_missing["custom_metadata"]
    assert durable_missing["word_count"] == 0


def test_trash_and_restore_are_logical_and_reversible(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Trash")
    slug = project["slug"]
    state = binder.get_binder(slug)
    draft = node_by_title(state, "Draft")
    chapter = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")
    path = storage.project_root(slug) / chapter.path

    trashed = binder.trash_node(slug, chapter.id)
    trash = node_by_title(trashed, "Trash")
    chapter_trashed = next(node for node in trashed.nodes if node.id == chapter.id)

    assert chapter_trashed.parent_id == trash.id
    assert chapter_trashed.previous_parent_id == draft.id
    assert path.exists()

    restored = binder.restore_node(slug, chapter.id)
    chapter_restored = next(node for node in restored.nodes if node.id == chapter.id)
    assert chapter_restored.parent_id == draft.id
    assert chapter_restored.previous_parent_id is None
    assert path.exists()


def test_binder_rejects_cycles_root_moves_and_orphans(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Cycles")
    slug = project["slug"]
    state = binder.get_binder(slug)
    story_bible = node_by_title(state, "Story Bible")

    state = binder.create_node(
        slug,
        BinderNodeCreate(title="Arc", kind="folder", parent_id=story_bible.id),
    )
    arc = node_by_title(state, "Arc")
    state = binder.create_node(
        slug,
        BinderNodeCreate(title="Nested", kind="folder", parent_id=arc.id),
    )
    nested = node_by_title(state, "Nested")

    with pytest.raises(ValueError, match="descendants"):
        binder.update_node(slug, arc.id, BinderNodeUpdate(parent_id=nested.id))

    with pytest.raises(ValueError, match="root"):
        binder.update_node(slug, story_bible.id, BinderNodeUpdate(parent_id=arc.id))

    with pytest.raises(ValueError, match="must have a parent"):
        binder.update_node(slug, arc.id, BinderNodeUpdate(parent_id=None))


def test_collection_references_stable_node_ids(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Binder Collections")
    slug = project["slug"]
    state = binder.get_binder(slug)
    chapter = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")

    state = binder.create_collection(
        slug,
        BinderCollectionCreate(
            name="Revision Pass",
            node_ids=[chapter.id],
            query="status:revise",
        ),
    )

    assert len(state.collections) == 1
    assert state.collections[0].name == "Revision Pass"
    assert state.collections[0].node_ids == [chapter.id]
