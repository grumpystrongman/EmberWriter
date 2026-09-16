import asyncio
from pathlib import Path

from app import craft, generation, routes_generation, storage
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count))


def test_inferno_is_controlling_intimacy_intent_even_with_generic_continue_prompt() -> None:
    assert generation.detect_scene_intent("Continue from here.", "inferno") == "intimacy"
    assert generation.detect_scene_intent("Continue from here.", "scorching") == "intimacy"
    assert generation.detect_scene_intent("Continue from here.", "hot") == "general"

    messages = generation.build_messages(
        "continue",
        "Continue from here.",
        "Older context contains a battle.",
        heat_level="inferno",
        min_scene_words=2200,
    )
    system = messages[0]["content"]
    assert "Scene intent: intimacy" in system
    assert "author's current instruction and explicit scene objective" in system
    assert "not merely a tone hint" in system
    assert "at least about 2200 words" in system
    assert generation.SCENE_COMPLETE_MARKER in system


def test_explicit_word_request_overrides_default_scene_floor() -> None:
    assert generation.scene_word_floor("Write this as a 900 word scene.", "inferno") == 900
    assert generation.scene_word_floor("Write a brief scene.", "inferno") == 700
    assert generation.scene_word_floor("Continue the scene.", "inferno") == 2200


def test_complete_scene_continues_across_generation_boundaries(monkeypatch) -> None:
    calls: list[list[dict[str, str]]] = []
    chunks = [
        _words("first", 700) + "\n" + generation.SCENE_CONTINUE_MARKER,
        _words("second", 800) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_generate(config, messages, **kwargs):
        calls.append(messages)
        assert kwargs["max_output_tokens"] == 6144
        return chunks.pop(0)

    monkeypatch.setattr(generation, "generate", fake_generate)
    result = asyncio.run(
        generation.generate_complete_prose(
            ProviderConfig(model="test-model"),
            [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
            min_words=1200,
        )
    )

    assert len(calls) == 2
    assert "first699" in calls[1][-2]["content"]
    assert "Continue the SAME scene seamlessly" in calls[1][-1]["content"]
    assert generation.SCENE_COMPLETE_MARKER not in result
    assert generation.SCENE_CONTINUE_MARKER not in result
    assert len(result.split()) == 1500


def test_complete_marker_does_not_allow_a_tiny_scene(monkeypatch) -> None:
    chunks = [
        _words("tiny", 250) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("finish", 800) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_generate(config, messages, **kwargs):
        return chunks.pop(0)

    monkeypatch.setattr(generation, "generate", fake_generate)
    result = asyncio.run(
        generation.generate_complete_prose(
            ProviderConfig(model="test-model"),
            [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
            min_words=1000,
        )
    )
    assert len(result.split()) == 1050


def test_active_tail_is_high_priority_continuation_anchor(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Tail Anchor")
    slug = project["slug"]
    beginning = "OPENING_BATTLE " + ("old " * 7000)
    ending = "CURRENT_SCENE " + ("latest " * 1000) + "FINAL_LINE"
    storage.save_text(slug, "manuscript/chapter-001.md", beginning + ending)

    context, files = routes_generation._with_active_tail(
        slug,
        "## Broad context\nOPENING_BATTLE",
        ["manuscript/chapter-001.md"],
        "manuscript/chapter-001.md",
    )

    anchor = context.split("\n\n---\n\n", 1)[0]
    assert "HIGH-PRIORITY ACTIVE CONTINUATION ANCHOR" in anchor
    assert "CURRENT_SCENE" in anchor
    assert "FINAL_LINE" in anchor
    assert "OPENING_BATTLE" not in anchor
    assert files[0] == "manuscript/chapter-001.md"


def test_craft_pass_refuses_truncated_second_pass(monkeypatch) -> None:
    draft = _words("draft", 1000)

    async def fake_generate(provider, messages, **kwargs):
        assert kwargs["max_output_tokens"] == 8192
        return _words("short", 200)

    monkeypatch.setattr(craft, "generate", fake_generate)
    result = asyncio.run(
        craft.quality_pass(
            ProviderConfig(model="test-model"),
            draft=draft,
            author_prompt="Preserve the complete scene.",
            craft_context="Voice locked.",
        )
    )
    assert result == draft
