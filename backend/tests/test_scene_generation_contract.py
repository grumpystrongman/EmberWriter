import asyncio
from pathlib import Path

from app import craft, generation, routes_generation, storage, streaming_generation, studio_context
from app.models import CraftControls, GenerateRequest, ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + "."


def test_inferno_is_controlling_intimacy_intent_even_with_generic_continue_prompt() -> None:
    assert generation.detect_scene_intent("Continue from here.", "inferno") == "intimacy"
    assert generation.detect_scene_intent("Continue from here.", "scorching") == "intimacy"
    assert generation.detect_scene_intent("Continue from here.", "hot") == "general"

    messages = generation.build_messages(
        "continue",
        "Continue from here.",
        "Older context contains a battle.",
        heat_level="inferno",
        min_scene_words=1600,
    )
    system = messages[0]["content"]
    assert "Scene intent: intimacy" in system
    assert "author's current instruction and explicit scene objective" in system
    assert "not merely a tone hint" in system
    assert "about 1600 words as an anti-fragment floor, not a quota" in system
    assert "Never add filler" in system
    assert "greater immediacy and forward motion, not more abstraction" in system
    assert generation.SCENE_COMPLETE_MARKER in system


def test_explicit_word_request_overrides_default_scene_floor() -> None:
    assert generation.scene_word_floor("Write this as a 900 word scene.", "inferno") == 900
    assert generation.scene_word_floor("Write a brief scene.", "inferno") == 700
    assert generation.scene_word_floor("Continue the scene.", "inferno") == 1600
    assert generation.scene_word_floor("Continue the scene.", "scorching") == 1400


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


def test_streamed_scene_becomes_visible_before_model_finishes(monkeypatch) -> None:
    visible: list[str] = []
    prose = _words("live", 80)
    raw = prose + "\n" + generation.SCENE_COMPLETE_MARKER

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        chunks = [raw[index:index + 24] for index in range(0, len(raw), 24)]
        saw_visible_before_return = False
        for index, chunk in enumerate(chunks):
            await on_delta(chunk)
            if index >= 4 and visible:
                saw_visible_before_return = True
        assert saw_visible_before_return is True
        return raw

    async def emit(text: str) -> None:
        visible.append(text)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
            min_words=60,
            on_delta=emit,
        )
    )

    streamed = "".join(visible)
    assert "live0" in streamed
    assert generation.SCENE_COMPLETE_MARKER not in streamed
    assert generation.SCENE_COMPLETE_MARKER not in result
    assert len(result.split()) == 80


def test_streamed_inferno_length_floor_keeps_going_after_short_complete_marker(monkeypatch) -> None:
    visible: list[str] = []
    calls = 0
    chunks = [
        _words("first", 682) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("second", 950) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal calls
        raw = chunks[calls]
        calls += 1
        await on_delta(raw)
        return raw

    async def emit(text: str) -> None:
        visible.append(text)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
            min_words=1600,
            on_delta=emit,
        )
    )

    assert calls == 2
    assert len(result.split()) == 1632
    assert generation.SCENE_COMPLETE_MARKER not in result


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


def test_studio_context_excludes_unrelated_manuscript_prose(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Studio Isolation")
    slug = project["slug"]

    storage.save_text(
        slug,
        "manuscript/chapter-001.md",
        "JAX_BATTLE_CONTAMINATION " + ("Kaelen academy gym fight Jax " * 500),
    )
    storage.save_text(
        slug,
        "characters/kaelen-thorne.md",
        "# Kaelen Thorne\n\nAdult Nexus. Calm, attentive, protective.\n",
    )
    storage.save_text(
        slug,
        "characters/muna.md",
        "# Muna\n\nAdult witch. Warm, playful, musical, joyful.\n",
    )
    storage.save_text(
        slug,
        "world/aethelgard-academy.md",
        "# Aethelgard Academy\n\nThe academy gym includes a sauna used after training.\n",
    )

    prompt = "Write a scene between Kaelen Thorne and Muna in the sauna at Aethelgard Academy after training."
    context, files, _, names = studio_context.build_studio_context(
        slug,
        prompt,
        CraftControls(heat_level="inferno"),
    )

    assert "JAX_BATTLE_CONTAMINATION" not in context
    assert not any(path.startswith("manuscript/") for path in files)
    assert not any(path.startswith("import/") for path in files)
    assert "Kaelen Thorne" in context
    assert "Muna" in context
    assert "Aethelgard Academy" in context
    assert "Every paragraph should do something new" in context
    assert "Never pad to reach a target" in context
    assert "Higher heat means greater immediacy" in context
    assert {name.casefold() for name in names} >= {"kaelen thorne", "muna"}


def test_studio_sentinel_routes_generation_through_isolated_context(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Studio Route")
    slug = project["slug"]
    storage.save_text(slug, "manuscript/chapter-001.md", "WRONG_JAX_SCENE Kaelen Jax fight " * 300)
    storage.save_text(slug, "characters/kaelen.md", "# Kaelen\n\nAdult Nexus.\n")
    storage.save_text(slug, "characters/muna.md", "# Muna\n\nAdult witch.\n")

    payload = GenerateRequest(
        prompt="Write a complete scene between Kaelen and Muna in the academy sauna.",
        mode="write",
        active_file=None,
        selected_text=studio_context.STUDIO_CONTEXT_SENTINEL,
        provider=ProviderConfig(model="test-model"),
        craft=CraftControls(heat_level="inferno"),
    )
    context, files, _ = routes_generation._prepare_generation_context(slug, payload)

    assert "WRONG_JAX_SCENE" not in context
    assert not any(path.startswith("manuscript/") for path in files)
    assert "Kaelen" in context
    assert "Muna" in context


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


def test_generation_context_budget_preserves_active_tail() -> None:
    separator = "\n\n---\n\n"
    context = (
        ("HIGH_PRIORITY_HEAD " * 6000)
        + separator
        + "## HIGH-PRIORITY ACTIVE CONTINUATION ANCHOR\nSource: manuscript/chapter.md\n\nCURRENT_ENDING_LINE"
        + separator
        + ("BROAD_STORY_TAIL " * 6000)
    )

    capped = routes_generation._cap_generation_context(context, max_chars=12000)

    assert len(capped) <= 12000
    assert "CURRENT_ENDING_LINE" in capped
    assert "HIGH_PRIORITY_HEAD" in capped
    assert "BROAD_STORY_TAIL" in capped


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
