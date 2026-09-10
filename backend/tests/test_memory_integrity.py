from __future__ import annotations

import json
from pathlib import Path

from app import memory, memory_integrity, storage


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def _analysis(subject: str, obj: str) -> dict:
    return {
        "summary": f"{subject} state summary",
        "facts": [
            {
                "kind": "canon",
                "subject": subject,
                "predicate": "is",
                "object": obj,
                "confidence": 0.98,
                "importance": 4,
            }
        ],
    }


def test_reconcile_removes_only_memory_from_changed_manuscript(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Memory Integrity")
    slug = project["slug"]
    first_path = "manuscript/chapter-001.md"
    second_path = "manuscript/chapter-002.md"

    first_original = "# Chapter 1\n\nThe key is beneath the chapel.\n"
    second_original = "# Chapter 2\n\nMara still carries the red ledger.\n"
    storage.save_text(slug, first_path, first_original)
    storage.save_text(slug, second_path, second_original)
    memory.store_analysis(slug, first_path, first_original, _analysis("key", "beneath chapel"))
    memory.store_analysis(slug, second_path, second_original, _analysis("Mara", "carries red ledger"))

    assert len(memory.list_memory(slug)) == 2

    storage.save_text(slug, first_path, "# Chapter 1\n\nThe key was never beneath the chapel.\n")
    result = memory_integrity.reconcile_story_memory(slug)

    assert result["stale_paths"] == [first_path]
    remaining = memory.list_memory(slug)
    assert len(remaining) == 1
    assert remaining[0]["source_path"] == second_path
    assert remaining[0]["subject"] == "Mara"
    assert memory.analysis_is_current(slug, second_path, second_original) is True

    exported = json.loads(
        (storage.project_root(slug) / "summaries" / "narrative-memory.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["path"] for item in exported["documents"]] == [second_path]
    assert [item["source_path"] for item in exported["facts"]] == [second_path]


def test_reconcile_removes_memory_for_deleted_source(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Deleted Memory Source")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    original = "# Chapter 1\n\nA lantern burns in the tower.\n"
    storage.save_text(slug, path, original)
    memory.store_analysis(slug, path, original, _analysis("lantern", "burns in tower"))

    (storage.project_root(slug) / path).unlink()
    result = memory_integrity.reconcile_story_memory(slug)

    assert result["stale_paths"] == [path]
    assert result["analyses_removed"] == 1
    assert result["facts_removed"] == 1
    assert memory.list_memory(slug) == []
