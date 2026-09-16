import asyncio

from app import generation, streaming_generation
from app.models import ProviderConfig


def _words(prefix: str, count: int, ending: str = ".") -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + ending


def test_dedupe_repetitive_prose_removes_near_duplicate_paragraphs() -> None:
    first = (
        "The heat of the sauna enveloped them, the steam thickening as they moved closer, "
        "the promise of release palpable in the air. Kaelen's hands moved to her hips, "
        "pulling her closer as Muna's hands moved to his back, her nails grazing his skin, "
        "sending waves of sensation through him."
    )
    repeated = (
        "The steam enveloped them, the heat pressing against their skin as they moved closer, "
        "the promise of release growing with every second. Kaelen's hands moved to her hips, "
        "pulling her closer as Muna's hands moved to his back, her nails grazing his skin, "
        "sending waves of sensation through him."
    )
    fresh = (
        "Muna broke the rhythm with a breathless laugh and pulled him toward the opposite bench. "
        "The change in position forced both of them to stop circling the same moment and choose what came next."
    )

    cleaned, removed, novelty = streaming_generation.dedupe_repetitive_prose(
        f"{repeated}\n\n{fresh}",
        first,
    )

    assert removed >= 1
    assert "breathless laugh" in cleaned
    assert "promise of release growing" not in cleaned
    assert 0 < novelty < 1


def test_streamed_completion_discards_loop_and_recovers(monkeypatch) -> None:
    visible: list[str] = []
    statuses: list[str] = []
    calls = 0

    base = (
        "The steam pressed around them while Kaelen held Muna close. "
        "Her hand moved over his back and he pulled her closer, both of them suspended in the same charged instant."
    )
    loop_one = (
        "The heat pressed around them while Kaelen held Muna close. "
        "Her hand moved over his back and he pulled her closer, both of them suspended in the same charged instant."
    )
    loop_two = (
        "The sauna heat surrounded them while Kaelen kept Muna close. "
        "Her hand moved over his back and he pulled her closer, both of them suspended in the same charged instant."
    )
    fresh = (
        _words("advance", 150)
        + " The scene finally changed state, the immediate consequence landed, and they were no longer circling the same beat."
    )

    chunks = [
        f"{base}\n\n{loop_one}\n\n{loop_two}\n{generation.SCENE_CONTINUE_MARKER}",
        f"{fresh}\n{generation.SCENE_COMPLETE_MARKER}",
    ]

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal calls
        raw = chunks[calls]
        calls += 1
        for index in range(0, len(raw), 43):
            await on_delta(raw[index:index + 43])
        return raw

    async def emit(text: str) -> None:
        visible.append(text)

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    messages = generation.build_messages(
        "write",
        "Write an intimate scene between two consenting adults.",
        "Canon context.",
        heat_level="inferno",
        min_scene_words=150,
    )
    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=150,
            on_delta=emit,
            on_status=status,
        )
    )

    assert calls == 2
    assert result.count("suspended in the same charged instant") == 1
    assert "advance149" in result
    assert any("Repetition loop detected" in message for message in statuses)
    streamed = "".join(visible)
    assert streamed.count("suspended in the same charged instant") == 1


def test_repeat_guard_does_not_remove_short_dialogue_refrain() -> None:
    candidate = '"Stay," she said.\n\n"Stay," he answered.'
    cleaned, removed, novelty = streaming_generation.dedupe_repetitive_prose(candidate)

    assert cleaned == candidate
    assert removed == 0
    assert novelty == 1.0
