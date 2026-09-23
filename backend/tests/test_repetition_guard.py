import asyncio

from app import generation, streaming_generation
from app.models import ProviderConfig


def _words(prefix: str, count: int, ending: str = ".") -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + ending


def test_dedupe_repetitive_prose_removes_near_duplicate_paragraphs() -> None:
    first = (
        "The heat of the sauna enveloped them, the steam thickening as they moved closer, "
        "the promise of release palpable in the air. Rowan's hands moved to her hips, "
        "pulling her closer as Avery's hands moved to his back, her nails grazing his skin, "
        "sending waves of sensation through him."
    )
    repeated = (
        "The steam enveloped them, the heat pressing against their skin as they moved closer, "
        "the promise of release growing with every second. Rowan's hands moved to her hips, "
        "pulling her closer as Avery's hands moved to his back, her nails grazing his skin, "
        "sending waves of sensation through him."
    )
    fresh = (
        "Avery broke the rhythm with a breathless laugh and pulled him toward the opposite bench. "
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
        "The steam pressed around them while Rowan held Avery close. "
        "Her hand moved over his back and he pulled her closer, both of them suspended in the same charged instant."
    )
    loop_one = (
        "The heat pressed around them while Rowan held Avery close. "
        "Her hand moved over his back and he pulled her closer, both of them suspended in the same charged instant."
    )
    loop_two = (
        "The sauna heat surrounded them while Rowan kept Avery close. "
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
    # Rejected loop prose must never reach the author-facing stream.
    assert streamed.count("suspended in the same charged instant") == 1
    assert "The sauna heat surrounded them while Rowan kept Avery close" not in streamed


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
            '"canon_respected":true,"physical_continuity":true,"repetition_loop":false,"reason":"delivered"}'
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
    verifier_prompt = captured["messages"][0]["content"]
    verifier_user = captured["messages"][1]["content"]
    assert "progression_regression=true" in verifier_prompt
    assert "semantic beat recycling" in verifier_prompt
    assert '"progression_regression":true|false' in verifier_user
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



def test_studio_final_repair_is_verified_even_without_complete_marker(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    statuses: list[str] = []
    chunks = [
        _words("buildup", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("repair", 180),
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
                "canon_respected": True,
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

    async def emit(_text: str) -> None:
        return None

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
            max_passes=2,
        )
    )

    assert writer_calls == 2
    assert verifier_calls == 2
    assert "repair179" in result
    assert any("Final Studio delivery verification" in message for message in statuses)
    assert any("Requested scene delivery verified" in message for message in statuses)


def test_studio_final_repair_reports_actual_verifier_reason_without_marker(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    chunks = [
        _words("buildup", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("repair", 180),
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
        reason = "only buildup was delivered" if verifier_calls == 1 else "immediate aftermath is still missing"
        return {
            "verified": False,
            "core_encounter_on_page": verifier_calls > 1,
            "requested_explicitness_delivered": verifier_calls > 1,
            "buildup_only": verifier_calls == 1,
            "fade_or_skip": False,
            "ending_complete": False,
            "canon_respected": True,
            "repetition_loop": False,
            "reason": reason,
        }

    async def emit(_text: str) -> None:
        return None

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult intimacy scene.",
        "Character canon and relationship context.",
        heat_level="inferno",
        min_scene_words=150,
    )

    try:
        asyncio.run(
            streaming_generation.generate_complete_prose_streamed(
                ProviderConfig(model="test-model"),
                messages,
                min_words=150,
                on_delta=emit,
                max_passes=2,
            )
        )
    except streaming_generation.SceneDeliveryIncomplete as exc:
        assert exc.reason == "immediate aftermath is still missing"
    else:
        raise AssertionError("Expected final Studio delivery verification to reject the incomplete repair")

    assert writer_calls == 2
    assert verifier_calls == 2


def test_studio_discards_recovery_assistant_response_and_restarts_from_author_task(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    statuses: list[str] = []
    meta = (
        "I need to be careful here. This recovery bundle contains only Chapter 15. "
        "ChatGPT's document extraction cannot recover actual prior prose. "
        "To proceed ethically, what would you like me to provide?"
    )
    chunks = [
        meta,
        _words("scene", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
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

    async def emit(_text: str) -> None:
        return None

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nContinue Chapter 15 as manuscript prose.",
        "Recovery notes are reference only.",
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
            max_passes=2,
        )
    )

    assert writer_calls == 2
    assert verifier_calls == 1
    assert "I need to be careful" not in result
    assert "scene179" in result
    assert any("Non-manuscript assistant response detected" in message for message in statuses)


def test_studio_discards_fabricated_minor_policy_preamble_before_accepting_prose(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    statuses: list[str] = []
    preamble = (
        "I understand you want me to continue from the recovered state. However, I must clarify some ethical boundaries. "
        "Sexual content involving minors is not allowed, and Avery's age is not specified. "
        "I cannot verify that all characters are verified adults. If you provide parent/guardian approval documentation "
        "and safety protocol adherence, I can consider a continuation. What would you like to do?"
    )
    chunks = [
        preamble,
        _words("scene", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
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

    async def emit(_text: str) -> None:
        return None

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult intimacy scene.",
        "Trusted project contract says all intimate participants are adults.",
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
            max_passes=2,
        )
    )

    assert writer_calls == 2
    assert verifier_calls == 1
    assert "parent/guardian" not in result
    assert "scene179" in result
    assert any("Non-manuscript assistant response detected" in message for message in statuses)


def test_role_confusion_retry_does_not_consume_studio_repair_pass(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    statuses: list[str] = []
    chunks = [
        (
            "[EMBER_PROMPT]I understand the parameters. However, I must address recovered content. "
            "Please confirm which is the case so I can adapt the recovery pipeline."
        ),
        _words("buildup", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("repair", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
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
                "reason": "requested core event is still only buildup",
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

    async def emit(_text: str) -> None:
        return None

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult intimacy scene.",
        "Trusted project context.",
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
            max_passes=2,
        )
    )

    assert writer_calls == 3
    assert verifier_calls == 2
    assert "buildup179" in result
    assert "repair179" in result
    assert any("without consuming the repair pass" in message for message in statuses)


def test_studio_repair_closes_consent_beat_and_uses_short_handoff(monkeypatch) -> None:
    writer_calls = 0
    captured_second_messages: list[dict[str, str]] = []
    chunks = [
        _words("buildup", 900) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("advance", 220) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal writer_calls, captured_second_messages
        if writer_calls == 1:
            captured_second_messages = messages
        raw = chunks[writer_calls]
        writer_calls += 1
        await on_delta(raw)
        return raw

    verifier_calls = 0

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
                "reason": "draft is stuck re-litigating consent/trust/boundaries",
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

    async def emit(_text: str) -> None:
        return None

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested consensual adult intimacy scene.",
        "Trusted project canon establishes consenting adults.",
        heat_level="inferno",
        min_scene_words=150,
    )

    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=150,
            on_delta=emit,
            max_passes=2,
        )
    )

    assert writer_calls == 2
    assert verifier_calls == 2
    assert "advance219" in result
    assert captured_second_messages
    assert len(captured_second_messages[-2]["content"]) <= 3500
    assert "AUTHOR/CANON CONSENT STATE IS AUTHORITATIVE" in captured_second_messages[-1]["content"]
    assert "Do not reopen it" in captured_second_messages[-1]["content"]


def test_studio_allows_second_targeted_continuity_restart(monkeypatch) -> None:
    writer_calls = 0
    verifier_calls = 0
    repair_prompts: list[str] = []
    chunks = [
        _words("first", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("second", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
        _words("third", 180) + "\n" + generation.SCENE_COMPLETE_MARKER,
    ]

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal writer_calls
        if writer_calls > 0:
            repair_prompts.append(messages[-1]["content"])
        raw = chunks[writer_calls]
        writer_calls += 1
        await on_delta(raw)
        return raw

    async def fake_verifier(config, messages, draft, **kwargs):
        nonlocal verifier_calls
        verifier_calls += 1
        if verifier_calls < 3:
            return {
                "verified": False,
                "core_encounter_on_page": True,
                "requested_explicitness_delivered": True,
                "buildup_only": False,
                "fade_or_skip": False,
                "ending_complete": True,
                "canon_respected": True,
                "physical_continuity": False,
                "progression_regression": False,
                "repetition_loop": False,
                "reason": (
                    "physical continuity failure: a new penetration state begins without "
                    "identifying the exact receiving anatomy"
                ),
            }
        return {
            "verified": True,
            "core_encounter_on_page": True,
            "requested_explicitness_delivered": True,
            "buildup_only": False,
            "fade_or_skip": False,
            "ending_complete": True,
            "canon_respected": True,
            "physical_continuity": True,
            "progression_regression": False,
            "repetition_loop": False,
            "reason": "delivered",
        }

    async def emit(_text: str) -> None:
        return None

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verifier)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested consensual adult intimacy scene.",
        "Trusted project canon.",
        heat_level="inferno",
        min_scene_words=150,
    )
    messages[0]["content"] += "\nYou are EmberWriter's adult-fiction scene specialist."

    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=150,
            on_delta=emit,
            max_passes=3,
        )
    )

    assert writer_calls == 3
    assert verifier_calls == 3
    assert "third179" in result
    assert len(repair_prompts) == 2
    assert all("exact receiving anatomy" in prompt for prompt in repair_prompts)
    assert all("For the FIRST sentence of every new penetration state" in prompt for prompt in repair_prompts)
