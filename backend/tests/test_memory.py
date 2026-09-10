import json
from pathlib import Path

from app import memory, storage


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_memory_store_search_export_and_replace(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Memory Novel")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    content = "# Chapter 1\n\nSera tells Jax the vault key is hidden beneath the chapel."
    storage.save_text(slug, path, content)

    result = memory.store_analysis(
        slug,
        path,
        content,
        {
            "summary": "Sera trusts Jax with the location of the vault key.",
            "facts": [
                {
                    "kind": "character_knowledge",
                    "subject": "Jax",
                    "predicate": "knows",
                    "object": "the vault key is hidden beneath the chapel",
                    "confidence": 1.0,
                    "importance": 5,
                },
                {
                    "kind": "relationship",
                    "subject": "Sera",
                    "predicate": "trusts",
                    "object": "Jax with the vault-key secret",
                    "confidence": 0.95,
                    "importance": 4,
                },
            ],
        },
    )

    assert result["facts_written"] == 2
    assert memory.analysis_is_current(slug, path, content)
    jax = memory.list_memory(slug, query="Jax vault key")
    assert jax[0]["importance"] >= 4
    assert any(item["kind"] == "character_knowledge" for item in jax)

    context = memory.build_memory_context(slug, query="Does Jax know about the key?")
    assert "Structured narrative memory" in context
    assert "hidden beneath the chapel" in context

    export_path = storage.project_root(slug) / "summaries" / "narrative-memory.json"
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert len(exported["facts"]) == 2
    assert exported["documents"][0]["summary"].startswith("Sera trusts Jax")

    changed = content + "\n\nLater, Jax gives the key to Elara."
    storage.save_text(slug, path, changed)
    assert not memory.analysis_is_current(slug, path, changed)

    memory.store_analysis(
        slug,
        path,
        changed,
        {
            "summary": "Jax passes the vault key to Elara.",
            "facts": [
                {
                    "kind": "object",
                    "subject": "vault key",
                    "predicate": "held by",
                    "object": "Elara",
                    "confidence": 1.0,
                    "importance": 5,
                }
            ],
        },
    )

    all_facts = memory.list_memory(slug)
    assert len(all_facts) == 1
    assert all_facts[0]["object"] == "Elara"
    assert memory.memory_stats(slug) == {
        "facts": 1,
        "documents": 1,
        "by_kind": {"object": 1},
    }


def test_memory_normalizes_invalid_model_facts(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Normalization")
    slug = project["slug"]
    path = "manuscript/chapter-012.md"
    content = "# Chapter 12\n\nMara reaches the observatory."
    storage.save_text(slug, path, content)

    memory.store_analysis(
        slug,
        path,
        content,
        {
            "summary": "Mara reaches the observatory.",
            "facts": [
                {
                    "kind": "location",
                    "subject": "Mara",
                    "predicate": "is at",
                    "object": "observatory",
                    "confidence": 4,
                    "importance": 99,
                },
                {
                    "kind": "made_up_kind",
                    "subject": "Mara",
                    "predicate": "likes",
                    "object": "tea",
                },
            ],
        },
    )

    facts = memory.list_memory(slug)
    assert len(facts) == 1
    assert facts[0]["chapter_order"] == 12
    assert facts[0]["confidence"] == 1.0
    assert facts[0]["importance"] == 5
