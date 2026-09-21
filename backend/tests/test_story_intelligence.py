import asyncio
import json
from pathlib import Path

from app import scene_architect, storage
from app.memory import store_analysis
from app.models import ProviderConfig, ScenePlanRequest
from app.story_intelligence import build_story_intelligence


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_story_intelligence_builds_character_profiles_and_relationships(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Intelligence Test")
    slug = project["slug"]
    storage.save_text(slug, "characters/mira.md", "# Mira\n\nCommanding, precise, and guarded.")
    storage.save_text(slug, "characters/tamsin.md", "# Tamsin\n\nBlunt, fierce, and protective.")

    chapter = "# Chapter 4\n\nSera tells Tamsin the vault key is hidden beneath the archive."
    storage.save_text(slug, "manuscript/chapter-004.md", chapter)
    store_analysis(
        slug,
        "manuscript/chapter-004.md",
        chapter,
        {
            "summary": "Mira trusts Tamsin with the vault-key secret.",
            "facts": [
                {
                    "kind": "character_knowledge",
                    "subject": "Tamsin",
                    "predicate": "knows",
                    "object": "the vault key is beneath the archive",
                    "confidence": 0.99,
                    "importance": 4,
                },
                {
                    "kind": "character_state",
                    "subject": "Mira",
                    "predicate": "has chosen",
                    "object": "to trust Tamsin with the vault secret",
                    "confidence": 0.95,
                    "importance": 4,
                },
                {
                    "kind": "relationship",
                    "subject": "Mira",
                    "predicate": "trusts",
                    "object": "Tamsin",
                    "confidence": 0.95,
                    "importance": 5,
                    "metadata": {"detail": "shares a dangerous secret"},
                },
            ],
        },
    )

    intelligence = build_story_intelligence(slug)
    profiles = {item["name"]: item for item in intelligence["characters"]}

    assert "Mira" in profiles
    assert "Tamsin" in profiles
    assert profiles["Tamsin"]["knowledge"][0]["predicate"] == "knows"
    assert profiles["Mira"]["state"][0]["chapter_order"] == 4
    assert any(
        edge["source"] == "Mira" and edge["target"] == "Tamsin" and edge["state"] == "trusts"
        for edge in intelligence["relationships"]
    )


def test_scene_architect_saves_valid_plan(tmp_path: Path, monkeypatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Scene Test")
    slug = project["slug"]
    storage.save_text(slug, "characters/mira.md", "# Mira\n\nA precise strategist.")
    storage.save_text(slug, "manuscript/chapter-002.md", "# Chapter 2\n\nSera reaches the locked archive.")

    async def fake_generate(*args, **kwargs):
        return json.dumps(
            {
                "title": "The Locked Archive",
                "pov": "Mira",
                "participants": ["Mira"],
                "location": "Archive",
                "scene_objective": "Open the archive without exposing her true motive.",
                "conflict": "The lock requires a truth Mira does not want to admit.",
                "opening_state": "Mira is controlled but under pressure.",
                "beats": [
                    {
                        "beat": "Mira tests the lock and learns it responds to confession.",
                        "purpose": "Turn the physical obstacle into an emotional one.",
                        "character_shift": "Control gives way to reluctant vulnerability.",
                    }
                ],
                "emotional_arc": "Control to vulnerability to renewed resolve.",
                "relationship_moves": [],
                "reveals": ["The archive lock responds to spoken truth."],
                "continuity_requirements": ["Mira has not entered the archive yet."],
                "unresolved_threads": ["Why Mira needs what is inside."],
                "intimacy_notes": [],
                "ending_state": "The archive opens after Mira admits part of the truth.",
                "next_scene_pressure": "Someone else heard the confession.",
            }
        )

    monkeypatch.setattr(scene_architect, "generate", fake_generate)
    request = ScenePlanRequest(
        prompt="Plan Mira opening the archive.",
        provider=ProviderConfig(model="test-model"),
        active_file="manuscript/chapter-002.md",
        pov="Mira",
        participants=["Mira"],
        location="Archive",
        save=True,
    )

    result = asyncio.run(scene_architect.create_scene_plan(slug, request))

    assert result["plan"].title == "The Locked Archive"
    assert result["saved_path"].startswith("scenes/scene-plan-")
    saved = json.loads(storage.read_text(slug, result["saved_path"]))
    assert saved["plan"]["scene_objective"].startswith("Open the archive")
    assert saved["author_request"] == "Plan Mira opening the archive."
