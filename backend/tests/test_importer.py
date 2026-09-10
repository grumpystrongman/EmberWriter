from pathlib import Path

import pytest

from app import binder, importer, revisions, storage


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "ember-data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"


def test_invalid_local_import_does_not_leave_orphan_project(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    source = tmp_path / "unsupported"
    source.mkdir()
    (source / "cover.png").write_bytes(b"not a supported story file")

    with pytest.raises(ValueError, match="No supported story files"):
        importer.import_project(str(source), "Should Not Exist")

    assert storage.list_projects() == []


def test_local_directory_import_is_revisioned_and_binder_synced(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    source = tmp_path / "source-book"
    (source / "manuscript").mkdir(parents=True)
    (source / "characters").mkdir()
    (source / "manuscript" / "chapter-one.md").write_text(
        "# Chapter One\n\nA real opening.\n",
        encoding="utf-8",
    )
    (source / "characters" / "mara.md").write_text(
        "# Mara\n\nA stubborn cartographer.\n",
        encoding="utf-8",
    )

    project = importer.import_project(str(source), "Imported Book")
    slug = project["slug"]
    assert "manuscript/chapter-one.md" in project["files"]
    assert "characters/mara.md" in project["files"]

    history = revisions.list_revisions(slug, "manuscript/chapter-one.md")
    assert len(history) == 1
    assert history[0]["source"] == "import"

    state = binder.get_binder(slug)
    chapter = next(node for node in state.nodes if node.path == "manuscript/chapter-one.md")
    character = next(node for node in state.nodes if node.path == "characters/mara.md")
    assert chapter.include_in_compile is True
    assert character.kind == "character"
