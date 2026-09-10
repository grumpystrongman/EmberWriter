from pathlib import Path

from app import binder, project_history, storage
from app.binder_models import BinderNodeCreate, BinderNodeUpdate


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_project_checkpoint_restores_files_and_binder_with_safety_snapshot(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Project History")
    slug = project["slug"]
    state = binder.get_binder(slug)
    draft = next(node for node in state.nodes if node.title == "Draft")
    first = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")
    assert first.path

    storage.save_text(slug, first.path, "# Chapter 1\n\nOriginal opening.\n")
    state = binder.update_node(
        slug,
        first.id,
        BinderNodeUpdate(synopsis="Original synopsis", status="Draft"),
    )
    checkpoint = project_history.create_project_checkpoint(
        slug,
        "Before rewrite",
        "Known-good manuscript state",
    )

    storage.save_text(slug, first.path, "# Chapter 1\n\nA rewrite I regret.\n")
    state = binder.update_node(
        slug,
        first.id,
        BinderNodeUpdate(synopsis="Changed synopsis", status="Rewritten"),
    )
    before_ids = {node.id for node in state.nodes}
    state = binder.create_node(
        slug,
        BinderNodeCreate(title="Temporary Scene", kind="document", parent_id=draft.id),
    )
    temporary = next(node for node in state.nodes if node.id not in before_ids)
    assert temporary.path and (storage.project_root(slug) / temporary.path).exists()

    comparison = project_history.compare_project_checkpoint(slug, checkpoint["id"])
    statuses = {(item["path"], item["status"]) for item in comparison["changes"]}
    assert (first.path, "modified") in statuses
    assert (temporary.path, "added") in statuses
    assert ("binder.json", "modified") in statuses

    restored = project_history.restore_project_checkpoint(slug, checkpoint["id"])
    assert restored["safety_checkpoint_id"] != checkpoint["id"]
    assert storage.read_text(slug, first.path) == "# Chapter 1\n\nOriginal opening.\n"
    assert not (storage.project_root(slug) / temporary.path).exists()

    restored_binder = binder.get_binder(slug)
    restored_first = next(node for node in restored_binder.nodes if node.id == first.id)
    assert restored_first.synopsis == "Original synopsis"
    assert restored_first.status == "Draft"
    assert all(node.id != temporary.id for node in restored_binder.nodes)

    exact = project_history.compare_project_checkpoint(slug, checkpoint["id"])
    assert exact["changed_files"] == 0
    assert exact["changes"] == []

    checkpoints = project_history.list_project_checkpoints(slug)
    safety = next(item for item in checkpoints if item["id"] == restored["safety_checkpoint_id"])
    assert safety["source"] == "pre_restore"


def test_project_restore_can_be_undone_using_pre_restore_checkpoint(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Undo Restore")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"

    storage.save_text(slug, path, "# Chapter 1\n\nVersion A\n")
    checkpoint_a = project_history.create_project_checkpoint(slug, "A")
    storage.save_text(slug, path, "# Chapter 1\n\nVersion B\n")

    restored = project_history.restore_project_checkpoint(slug, checkpoint_a["id"])
    assert storage.read_text(slug, path).endswith("Version A\n")
    assert project_history.compare_project_checkpoint(slug, checkpoint_a["id"])["changed_files"] == 0

    project_history.restore_project_checkpoint(slug, restored["safety_checkpoint_id"])
    assert storage.read_text(slug, path).endswith("Version B\n")
    assert (
        project_history.compare_project_checkpoint(slug, restored["safety_checkpoint_id"])[
            "changed_files"
        ]
        == 0
    )
