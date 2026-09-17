import asyncio

import pytest

from app import generation, generation_reliability, streaming_generation
from app.models import ProviderConfig


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + "."


def test_under_word_limit_overrides_inferno_floor() -> None:
    prompt = (
        "Write a complete adult intimacy scene between two consenting adults. "
        "Keep it under 1300 words and finish the requested scene."
    )
    contract = generation_reliability.parse_scene_length(prompt, "inferno")

    assert contract.max_words == 1300
    assert contract.floor_words == 715
    assert contract.target_words == 1066
    assert generation.scene_word_floor(prompt, "inferno") == 715


def test_word_ceiling_is_written_into_the_model_contract() -> None:
    prompt = "Write the requested consenting-adult intimacy scene under 1300 words."
    floor = generation.scene_word_floor(prompt, "inferno")
    messages = generation.build_messages(
        "write",
        prompt,
        "Character canon only.",
        heat_level="inferno",
        min_scene_words=floor,
    )

    system = messages[0]["content"]
    assert "HARD CEILING" in system
    assert "under 1300 words" in system
    assert "around 1066 words" in system
    assert "higher priority than generic heat-length defaults" in system
    assert "about 715 words as an anti-fragment floor" in system


def test_continuation_token_budget_shrinks_against_remaining_word_ceiling() -> None:
    prompt = "Write the complete scene under 1300 words."
    floor = generation.scene_word_floor(prompt, "inferno")
    messages = generation.build_messages(
        "write",
        prompt,
        "Canon.",
        heat_level="inferno",
        min_scene_words=floor,
    )
    messages.extend(
        [
            {"role": "assistant", "content": _words("draft", 1000)},
            {"role": "user", "content": "Continue the same scene and finish it."},
        ]
    )

    budget = generation_reliability._remaining_output_tokens(messages, 6144)
    assert budget is not None
    assert 350 <= budget <= 450


def test_range_word_request_has_floor_and_hard_ceiling() -> None:
    contract = generation_reliability.parse_scene_length(
        "Write this scene in 900-1200 words.",
        "inferno",
    )
    assert contract.floor_words == 900
    assert contract.target_words == 1050
    assert contract.max_words == 1200


def test_adult_model_ranking_prefers_creative_rp_models_over_qwen_fallbacks() -> None:
    assert generation_reliability.adult_model_score(
        "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"
    ) > generation_reliability.adult_model_score(
        "HammerAI/rocinante-v1.1:12b-q4_K_M"
    )
    assert generation_reliability.adult_model_score(
        "HammerAI/rocinante-v1.1:12b-q4_K_M"
    ) > generation_reliability.adult_model_score(
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m"
    )


def test_runaway_single_sentence_is_discarded_before_it_can_finish_streaming() -> None:
    visible: list[str] = []

    async def emit(text: str) -> None:
        visible.append(text)

    async def exercise() -> tuple[str, str]:
        guard = streaming_generation._NoveltyStreamFilter(emit)
        runaway = " ".join(f"association{index}" for index in range(180))
        chunks = [runaway[index:index + 48] for index in range(0, len(runaway), 48)]
        with pytest.raises(streaming_generation.RepetitionLoopDetected):
            for chunk in chunks:
                await guard.feed(chunk)
        return guard.text, "".join(visible)

    accepted, streamed = asyncio.run(exercise())
    assert accepted == ""
    # A small prefix can be visible because Studio streams live, but the guard interrupts
    # before the hundreds-of-words lexical collapse observed in the regression sample.
    assert len(streamed.split()) < 120


def test_deterministic_quality_gate_rejects_observed_runaway_shape() -> None:
    bad = "Muna smiled. " + " ".join(f"meaning{index}" for index in range(160)) + "."
    reason = generation_reliability._hard_quality_failure(bad)
    assert "Runaway syntax detected" in reason


def test_streamed_hard_ceiling_uses_compression_only_when_needed(monkeypatch) -> None:
    prompt = "Write a complete consenting-adult intimacy scene under 1300 words."
    floor = generation.scene_word_floor(prompt, "inferno")
    messages = generation.build_messages(
        "write",
        prompt,
        "Canon.",
        heat_level="inferno",
        min_scene_words=floor,
    )
    oversized = _words("draft", 1400)
    compressed = _words("tight", 1050)
    compress_calls = 0

    async def fake_complete(*args, **kwargs):
        return oversized

    async def fake_compress(config, source_messages, draft, maximum):
        nonlocal compress_calls
        compress_calls += 1
        assert maximum == 1300
        assert draft == oversized
        return compressed

    async def emit(_: str) -> None:
        return None

    monkeypatch.setattr(generation_reliability, "_original_generate_complete_streamed", fake_complete)
    monkeypatch.setattr(generation_reliability, "_compress_to_author_ceiling", fake_compress)

    result = asyncio.run(
        generation_reliability.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=floor,
            on_delta=emit,
        )
    )

    assert compress_calls == 1
    assert len(result.split()) == 1050
