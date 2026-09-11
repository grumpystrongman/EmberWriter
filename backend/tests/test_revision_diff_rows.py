from pathlib import Path

from app import revisions, storage


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Diff Test")["slug"]


def test_side_by_side_revision_rows_align_changes(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    older_text = "# Chapter 1\n\nOne line.\nTwo line.\nThree line.\n"
    newer_text = "# Chapter 1\n\nOne line.\nTwo changed.\nInserted line.\nThree line.\n"

    storage.save_text(slug, path, older_text)
    older = revisions.record_revision(slug, path, older_text, source="save")
    storage.save_text(slug, path, newer_text)
    newer = revisions.record_revision(slug, path, newer_text, source="save")

    compared = revisions.compare_revisions(slug, older["id"], newer["id"])
    rows = compared["rows"]

    assert any(row["kind"] == "change" and row["older_text"] == "Two line." and row["newer_text"] == "Two changed." for row in rows)
    assert any(row["kind"] == "insert" and row["newer_text"] == "Inserted line." for row in rows)
    assert any(row["kind"] == "equal" and row["older_text"] == "Three line." and row["newer_text"] == "Three line." for row in rows)
    assert compared["diff"].startswith("--- revision:")


def test_side_by_side_diff_against_current_document(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    older_text = "# Chapter 1\n\nThe old sentence.\n"
    current_text = "# Chapter 1\n\nThe current sentence.\n"

    storage.save_text(slug, path, older_text)
    older = revisions.record_revision(slug, path, older_text, source="checkpoint", force=True)
    storage.save_text(slug, path, current_text)

    compared = revisions.compare_revisions(slug, older["id"])
    assert compared["newer"]["id"] == "current"
    assert any(row["kind"] == "change" for row in compared["rows"])
