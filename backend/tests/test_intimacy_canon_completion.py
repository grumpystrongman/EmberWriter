import asyncio
from pathlib import Path

from app import generation, generation_reliability_refinement, storage, story_intelligence
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
        "characters/avery.md",
        (
            "# Avery\n\n"
            + filler
            + "\n\n## Embodiment & intimate canon\n"
            + "Avery is an adult trans woman. Avery has a penis. Avery does not have a vagina, vulva, or clitoris. BODY_CANON_SENTINEL: do not invent anatomy that contradicts this dossier.\n"
        ),
    )

    context = story_intelligence.build_character_context(slug, ["Avery"])

    assert "BODY_CANON_SENTINEL" in context
    assert "HARD BODY / EMBODIMENT CANON" in context
    assert "Avery has a penis" in context
    assert "Avery does not have a vagina, vulva, or clitoris" in context
    assert "hard canon" in context
    assert "do not infer intimate anatomy" in context.lower()


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


def test_body_canon_gate_rejects_explicitly_absent_anatomy() -> None:
    context = """## Character intelligence
### Avery
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Avery has a penis. Avery does not have a vagina, vulva, or clitoris.
### Rowan
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Rowan has a penis.
"""
    bad = "Avery pulled Rowan closer. He touched her clitoris while she held him."
    reason = generation_reliability_refinement.hard_body_canon_failure(context, bad)
    assert "hard body-canon conflict" in reason
    assert "Avery" in reason


def test_body_canon_gate_does_not_infer_absence_from_trans_identity() -> None:
    context = """## Character intelligence
### Avery
Avery is an adult trans woman.
"""
    assert generation_reliability_refinement.hard_body_canon_failure(
        context,
        "Avery touched her body.",
    ) == ""


def test_body_canon_gate_rejects_implicit_vaginal_template_when_not_established() -> None:
    context = """## Character intelligence
### Muna
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Muna has a penis. Muna does not have a vagina, vulva, or clitoris.
### Kaelen
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Kaelen has a penis.
"""
    bad = (
        "Kaelen's mouth closed over her slick entrance while his hand held Muna's cock. "
        "The folds trembled under his mouth."
    )
    reason = generation_reliability_refinement.hard_body_canon_failure(context, bad)
    assert "vague cis-female-template receptive anatomy" in reason


def test_body_canon_gate_allows_named_anal_anatomy_with_same_canon() -> None:
    context = """## Character intelligence
### Muna
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Muna has a penis. Muna does not have a vagina, vulva, or clitoris.
### Kaelen
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Kaelen has a penis.
"""
    draft = "Kaelen moved behind Muna and touched her anus before they changed position."
    assert generation_reliability_refinement.hard_body_canon_failure(context, draft) == ""


def test_requested_position_gate_requires_missionary_geometry() -> None:
    prompt = "explicit missionary sex, doggy style sex, anal, blowjob"
    draft = (
        "Avery went onto hands and knees facing away while Rowan knelt behind her. "
        "Rowan touched Avery's anus and they later had oral sex with her penis. "
        "They reached a clear orgasm together."
    )
    reason = generation_reliability_refinement.requested_act_delivery_failure(prompt, draft)
    assert "missionary" in reason
    assert "receiver-on-back" in reason


def test_requested_position_gate_accepts_recognizable_requested_sequence() -> None:
    prompt = "explicit missionary sex, doggy style sex, anal, blowjob"
    draft = (
        "Avery lay on her back with her legs apart while Rowan moved between her legs facing her. "
        "Later Avery moved onto hands and knees facing away and Rowan knelt behind her. "
        "He identified her anus before anal penetration. "
        "After they changed position, Avery used her mouth on Rowan's cock for oral sex."
    )
    assert generation_reliability_refinement.requested_act_delivery_failure(prompt, draft) == ""


def test_requested_position_gate_respects_negated_position() -> None:
    prompt = "explicit anal scene, avoid missionary, include doggy style and blowjob"
    draft = (
        "Avery moved onto hands and knees facing away while Rowan knelt behind her. "
        "He identified her anus before anal penetration. "
        "Afterward she used her mouth on Rowan's penis."
    )
    assert generation_reliability_refinement.requested_act_delivery_failure(prompt, draft) == ""


def test_requested_position_gate_accepts_missionary_across_adjacent_paragraphs() -> None:
    prompt = "explicit missionary sex, doggy style sex, anal, blowjob"
    draft = (
        "Avery lay on her back with her legs apart while Rowan faced her between her legs.\n\n"
        "Rowan began anal penetration and thrust carefully while Avery stayed on her back.\n\n"
        "Avery then moved onto hands and knees facing away while Rowan knelt behind her and continued penetrative action at her anus.\n\n"
        "After they changed position, Avery used her mouth on Rowan's cock for oral sex."
    )

    assert generation_reliability_refinement.requested_act_delivery_failure(prompt, draft) == ""


def test_requested_position_gate_does_not_merge_nonlocal_missionary_signals() -> None:
    prompt = "explicit missionary sex"
    draft = (
        "Avery lay on her back with her legs apart while Rowan faced her between her legs.\n\n"
        "They stopped, stood up, crossed the room, and changed to a completely different position.\n\n"
        "Much later Rowan began penetration from behind."
    )

    reason = generation_reliability_refinement.requested_act_delivery_failure(prompt, draft)

    assert "missionary" in reason
    assert "local beat window" in reason
