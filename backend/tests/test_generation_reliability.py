import asyncio

import pytest

from app import (
    generation,
    generation_reliability,
    generation_reliability_refinement,
    streaming_generation,
)
from app.models import ProviderConfig


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + "."


def _semantic_chain() -> str:
    seed = (
        "connection memory essence soul destiny eternity sacred foundation growth development evolution "
        "progression advancement improvement transformation manifestation recognition appreciation valuation "
        "judgment determination choice belief faith doctrine principle legacy tradition honor admiration success "
        "achievement triumph victory domination power strength vitality capability potential probability ambiguity "
        "complexity harmony unity integrity wholeness completeness richness intensity consequence aftermath desire "
        "longing yearning lust passion consent permission approval validation authorization alignment synchrony agreement "
        "bind unite expand intensify reinforce preserve control regulate manage guide teach enlighten discovery "
        "understanding knowledge wisdom truth reality awareness consciousness experience embodiment existence purpose meaning"
    )
    # Repeat the same semantic field with connective language to reproduce the production failure's
    # punctuation-starved association drift rather than merely constructing a long sentence.
    return f"{seed} and then {seed}"


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


def test_between_word_range_beats_incidental_first_word_count() -> None:
    contract = generation_reliability.parse_scene_length(
        "Begin direct action within the first 140 words. Keep the complete scene between 900 and 1600 words.",
        "inferno",
    )
    assert contract.floor_words == 900
    assert contract.target_words == 1250
    assert contract.max_words == 1600


def test_adult_model_ranking_prefers_creative_rp_models_over_qwen_fallbacks() -> None:
    assert generation_reliability.adult_model_score(
        "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"
    ) > generation_reliability.adult_model_score(
        "HammerAI/rocinante-v1.1:12b-q4_K_M"
    )
    assert generation_reliability.adult_model_score(
        "HammerAI/rocinante-v1.1:12b-q4_K_M"
    ) > generation_reliability.adult_model_score(
        "TheDrummer/Cydonia-24B-v4.3:Q4_K_M"
    )
    assert generation_reliability.adult_model_score(
        "HammerAI/rocinante-v1.1:12b-q4_K_M"
    ) > generation_reliability.adult_model_score(
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m"
    )


def test_long_synthetic_sentence_is_not_mistaken_for_semantic_degeneration() -> None:
    synthetic = _words("advance", 1000)
    assert generation_reliability_refinement.looks_like_semantic_chain(synthetic) is False
    assert generation_reliability._hard_quality_failure(synthetic) == ""


def test_runaway_semantic_chain_is_never_forwarded_to_visible_stream() -> None:
    visible: list[str] = []

    async def emit(text: str) -> None:
        visible.append(text)

    async def exercise() -> tuple[str, str]:
        guard = streaming_generation._NoveltyStreamFilter(emit)
        runaway = _semantic_chain()
        chunks = [runaway[index:index + 48] for index in range(0, len(runaway), 48)]
        with pytest.raises(streaming_generation.RepetitionLoopDetected):
            for chunk in chunks:
                await guard.feed(chunk)
        await guard.finish()
        return guard.text, "".join(visible)

    accepted, streamed = asyncio.run(exercise())
    assert accepted == ""
    assert streamed == ""


def test_deterministic_quality_gate_rejects_observed_runaway_shape() -> None:
    bad = "Avery smiled. " + _semantic_chain() + "."
    reason = generation_reliability._hard_quality_failure(bad)
    assert "semantic-chain degeneration" in reason


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


def test_hard_quality_gate_rejects_runaway_repeated_word() -> None:
    reason = generation_reliability_refinement.hard_quality_failure(
        "The contact was electric, electric, electric. They kept moving."
    )
    assert "runaway repeated word" in reason


def test_hard_quality_gate_rejects_multiple_recycled_short_sentences() -> None:
    draft = (
        "This is amazing and I can feel you. The room seemed to disappear. "
        "This is beautiful and I feel every bit of you. They shifted position. "
        "This is amazing and I can feel you. The rhythm changed. "
        "This is beautiful and I feel every bit of you."
    )
    reason = generation_reliability_refinement.hard_quality_failure(draft)
    assert "short sentences are being recycled" in reason
    assert "2x 'this is amazing and i can feel you'" in reason
    assert "2x 'this is beautiful and i feel every bit of you'" in reason
