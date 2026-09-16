import asyncio
from pathlib import Path

from app import generation, storage, story_intelligence
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def _words(prefix: str, count: int, ending: str = ".") -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + ending


def test_system_prompt_forbids_inferred_intimate_anatomy() -> None:
    messages = generation.build_messages(
        "write",
        "Write an intimate scene between two adult characters.",
        "One character is a trans woman.",
        heat_level="inferno",
        min_scene_words=2200,
    )
    system = messages[0]["content"]

    assert "Never infer genitals" in system
    assert "womanhood or manhood never implies a particular set of genitals" in system
    assert "do not make a creative guess" in system
    assert "buildup, kissing, or merely beginning the encounter is not completion" in system


def test_character_context_keeps_late_embodiment_canon_visible(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Embodiment Canon")
    slug = project["slug"]
    filler = "background detail " * 360
    storage.save_text(
        slug,
        "characters/muna.md",
        (
            "# Muna\n\n"
            + filler
            + "\n\n## Embodiment & intimate canon\n"
            + "Muna is an adult trans woman. BODY_CANON_SENTINEL: do not invent anatomy that contradicts this dossier.\n"
        ),
    )

    context = story_intelligence.build_character_context(slug, ["Muna"])

    assert "BODY_CANON_SENTINEL" in context
    assert "hard canon" in context
    assert "do not infer intimate anatomy" in context


def test_intimacy_scene_does_not_accept_word_floor_without_complete_marker(monkeypatch) -> None:
    calls = 0
    chunks = [
        _words("first", 1200),
        _words("second", 300) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_generate(config, messages, **kwargs):
        nonlocal calls
        result = chunks[calls]
        calls += 1
        return result

    monkeypatch.setattr(generation, "generate", fake_generate)
    messages = generation.build_messages(
        "write",
        "Write an intimate scene.",
        "Adult characters.",
        heat_level="inferno",
        min_scene_words=1000,
    )
    result = asyncio.run(
        generation.generate_complete_prose(
            ProviderConfig(model="test-model"),
            messages,
            min_words=1000,
        )
    )

    assert calls == 2
    assert "second299" in result
    assert generation.SCENE_COMPLETE_MARKER not in result


def test_complete_marker_cannot_accept_mid_sentence_truncation(monkeypatch) -> None:
    calls = 0
    chunks = [
        ("word " * 1100).rstrip() + " the worl\n" + generation.SCENE_COMPLETE_MARKER,
        _words("finish", 120) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_generate(config, messages, **kwargs):
        nonlocal calls
        result = chunks[calls]
        calls += 1
        return result

    monkeypatch.setattr(generation, "generate", fake_generate)
    messages = generation.build_messages(
        "write",
        "Write an intimate scene.",
        "Adult characters.",
        heat_level="inferno",
        min_scene_words=1000,
    )
    result = asyncio.run(
        generation.generate_complete_prose(
            ProviderConfig(model="test-model"),
            messages,
            min_words=1000,
        )
    )

    assert calls == 2
    assert result.endswith(".")
    assert "finish119" in result


def test_non_intimacy_scene_can_still_accept_a_natural_multi_pass_ending(monkeypatch) -> None:
    calls = 0
    chunks = [_words("first", 600), _words("second", 600)]

    async def fake_generate(config, messages, **kwargs):
        nonlocal calls
        result = chunks[calls]
        calls += 1
        return result

    monkeypatch.setattr(generation, "generate", fake_generate)
    messages = generation.build_messages(
        "write",
        "Write a training scene.",
        "Academy gym.",
        heat_level="hot",
        min_scene_words=1000,
    )
    result = asyncio.run(
        generation.generate_complete_prose(
            ProviderConfig(model="test-model"),
            messages,
            min_words=1000,
        )
    )

    assert calls == 2
    assert len(result.split()) >= 1200
