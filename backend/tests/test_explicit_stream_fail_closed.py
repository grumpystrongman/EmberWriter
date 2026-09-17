import asyncio

import pytest

from app import explicit_delivery_policy as policy
from app import streaming_generation
from app.models import ProviderConfig


def _explicit_messages() -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "Scene intent: intimacy\nRequested heat: inferno.",
        },
        {
            "role": "user",
            "content": (
                "AUTHOR INSTRUCTION\n"
                "Write an explicit consenting-adult sex scene with penetration, genitalia, and orgasm.\n\n"
                "PROJECT CONTEXT\nAdults only."
            ),
        },
    ]


def test_rejected_explicit_stream_never_reaches_author_delta(monkeypatch) -> None:
    visible: list[str] = []

    async def emit(text: str) -> None:
        visible.append(text)

    async def fake_base(config, messages, *, on_delta, **kwargs):
        await on_delta(
            "They undressed, kissed, and became one before reaching a shared climax together."
        )
        raise streaming_generation.SceneDeliveryIncomplete(
            "They undressed, kissed, and became one before reaching a shared climax together.",
            "explicit delivery rejected",
        )

    monkeypatch.setattr(policy, "_base_generate_complete_prose_streamed", fake_base)

    with pytest.raises(streaming_generation.SceneDeliveryIncomplete):
        asyncio.run(
            policy.strict_generate_complete_prose_streamed(
                ProviderConfig(model="test-model"),
                _explicit_messages(),
                min_words=500,
                on_delta=emit,
            )
        )

    assert visible == []


def test_verified_explicit_stream_is_released_only_after_success(monkeypatch) -> None:
    visible: list[str] = []
    direct = (
        "The consenting adults checked in clearly.\n\n"
        "He touched her clitoris and penetrated her vagina while she guided the pace. "
        "She came, then he orgasmed."
    )

    async def emit(text: str) -> None:
        visible.append(text)

    async def fake_base(config, messages, *, on_delta, **kwargs):
        # This simulates many live model deltas. They must remain private until validation passes.
        await on_delta(direct[:50])
        await on_delta(direct[50:])
        return direct

    monkeypatch.setattr(policy, "_base_generate_complete_prose_streamed", fake_base)

    result = asyncio.run(
        policy.strict_generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            _explicit_messages(),
            min_words=50,
            on_delta=emit,
        )
    )

    assert result == direct
    assert visible == [direct]


def test_non_direct_intimacy_keeps_normal_live_stream(monkeypatch) -> None:
    visible: list[str] = []
    messages = [
        {"role": "system", "content": "Scene intent: intimacy\nRequested heat: inferno."},
        {
            "role": "user",
            "content": (
                "AUTHOR INSTRUCTION\nWrite a complete adult intimacy scene.\n\n"
                "PROJECT CONTEXT\nAdults only."
            ),
        },
    ]

    async def emit(text: str) -> None:
        visible.append(text)

    async def fake_base(config, source_messages, *, on_delta, **kwargs):
        await on_delta("live prose")
        return "live prose"

    monkeypatch.setattr(policy, "_base_generate_complete_prose_streamed", fake_base)

    result = asyncio.run(
        policy.strict_generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=50,
            on_delta=emit,
        )
    )

    assert result == "live prose"
    assert visible == ["live prose"]
