from pathlib import Path

from app import storage


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_project_round_trip_and_snapshot_restore(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Test Novel")
    slug = project["slug"]

    assert "manuscript/chapter-001.md" in project["files"]

    storage.save_text(slug, "manuscript/chapter-001.md", "# Chapter 1\n\nSera enters the archive.")
    second = storage.save_text(
        slug,
        "manuscript/chapter-001.md",
        "# Chapter 1\n\nSera enters the archive and finds the sealed letter.",
    )

    assert second["snapshot_id"] is not None
    assert "sealed letter" in storage.read_text(slug, "manuscript/chapter-001.md")

    snapshots = storage.list_snapshots(slug, "manuscript/chapter-001.md")
    assert snapshots
    storage.restore_snapshot(slug, snapshots[0]["id"])
    assert storage.read_text(slug, "manuscript/chapter-001.md").endswith("Sera enters the archive.")


def test_search_and_context_compiler(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Memory Test")
    slug = project["slug"]
    storage.save_text(slug, "characters/jax.md", "# Jax\n\nJax distrusts the silver council but protects Elara.")
    storage.save_text(slug, "world/council.md", "# Silver Council\n\nThe council meets beneath the western tower.")

    hits = storage.search_story(slug, "What does Jax know about the silver council?")
    assert any(hit["path"] == "characters/jax.md" for hit in hits)

    context, files = storage.compile_context(slug, prompt="Jax confronts the silver council")
    assert "characters/jax.md" in files
    assert "Jax distrusts" in context
