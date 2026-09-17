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
    assert "advance149" in streamed


def test_repeat_guard_does_not_remove_short_dialogue_refrain() -> None:
    candidate = '"Stay," she said.\n\n"Stay," he answered.'
    cleaned, removed, novelty = streaming_generation.dedupe_repetitive_prose(candidate)

    assert cleaned == candidate
    assert removed == 0
    assert novelty == 1.0


def test_studio_delivery_verifier_requires_every_delivery_dimension(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_generate(config, messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return (
            '{"core_encounter_on_page":true,"requested_explicitness_delivered":true,'
            '"buildup_only":false,"fade_or_skip":false,"ending_complete":true,'
            '"canon_respected":true,"repetition_loop":false,"reason":"delivered"}'
        )

    monkeypatch.setattr(streaming_generation, "generate_text", fake_generate)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult intimacy scene.",
        "Character canon and relationship context.",
        heat_level="inferno",
        min_scene_words=1000,
    )
    verdict = asyncio.run(
        streaming_generation.verify_studio_scene_delivery(
            ProviderConfig(
                provider="openai_compatible",
                base_url="http://example.test/v1",
                model="test-model",
            ),
            messages,
            _words("draft", 1000),
        )
    )

    assert verdict["verified"] is True
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["json_mode"] is True
    assert kwargs["temperature"] == 0.0


def test_studio_rejects_buildup_even_when_writer_claims_complete(monkeypatch) -> None:
    visible: list[str] = []
    statuses: list[str] = []
    writer_calls = 0
    verifier_calls = 0
    chunks = [
        _words("buildup", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("advance", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal writer_calls
        raw = chunks[writer_calls]
        writer_calls += 1
        await on_delta(raw)
        return raw

    async def fake_verifier(config, messages, draft, **kwargs):
        nonlocal verifier_calls
        verifier_calls += 1
        if verifier_calls == 1:
            return {
                "verified": False,
                "core_encounter_on_page": False,
                "requested_explicitness_delivered": False,
                "buildup_only": True,
                "fade_or_skip": False,
                "ending_complete": False,
                "canon_respected": True,
                "repetition_loop": False,
                "reason": "only buildup was delivered",
            }
        return {
            "verified": True,
            "core_encounter_on_page": True,
            "requested_explicitness_delivered": True,
            "buildup_only": False,
            "fade_or_skip": False,
            "ending_complete": True,
            "canon_respected": True,
            "repetition_loop": False,
            "reason": "delivered",
        }

    async def emit(text: str) -> None:
        visible.append(text)

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult intimacy scene.",
        "Character canon and relationship context.",
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

    assert writer_calls == 2
    assert verifier_calls == 2
    assert "buildup179" in result
    assert "advance179" in result
    assert any("Delivery check failed" in message for message in statuses)
    assert any("Requested scene delivery verified" in message for message in statuses)
