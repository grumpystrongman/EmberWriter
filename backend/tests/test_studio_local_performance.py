import asyncio

import app.generation_reliability as reliability
import app.generation_reliability_refinement as refinement
import app.local_model_stream_reliability as local_stream
import app.streaming_generation as streaming_generation
import app.studio_local_performance as performance
from app.models import ProviderConfig


STUDIO_MESSAGES = [
    {"role": "system", "content": "Scene intent: intimacy\nSTUDIO SCENE DELIVERY CONTRACT:"},
    {"role": "user", "content": "AUTHOR INSTRUCTION\nWrite the requested scene."},
]


async def _noop_delta(_text: str) -> None:
    return None


def test_local_studio_caps_generation_at_two_prose_passes(monkeypatch) -> None:
    observed: dict[str, int] = {}
    statuses: list[str] = []

    async def fake_base(*_args, **kwargs) -> str:
        observed["max_passes"] = kwargs["max_passes"]
        return "draft"

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(performance, "_BASE_STREAMED_COMPLETE", fake_base)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="test")

    result = asyncio.run(
        performance.generate_complete_prose_streamed_budgeted(
            config,
            STUDIO_MESSAGES,
            min_words=300,
            on_delta=_noop_delta,
            on_status=status,
            max_passes=6,
        )
    )

    assert result == "draft"
    assert observed["max_passes"] == 2
    assert any("one repair pass maximum" in message for message in statuses)


def test_nonlocal_generation_keeps_caller_pass_budget(monkeypatch) -> None:
    observed: dict[str, int] = {}

    async def fake_base(*_args, **kwargs) -> str:
        observed["max_passes"] = kwargs["max_passes"]
        return "draft"

    monkeypatch.setattr(performance, "_BASE_STREAMED_COMPLETE", fake_base)
    config = ProviderConfig(
        provider="openai_compatible",
        base_url="http://example.test/v1",
        model="test",
    )

    asyncio.run(
        performance.generate_complete_prose_streamed_budgeted(
            config,
            STUDIO_MESSAGES,
            min_words=300,
            on_delta=_noop_delta,
            max_passes=6,
        )
    )

    assert observed["max_passes"] == 6


def test_deterministic_explicitness_failure_skips_llm_verifier(monkeypatch) -> None:
    called = False

    async def expensive_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True}

    monkeypatch.setattr(performance, "_BASE_VERIFY", expensive_verify)
    monkeypatch.setattr(reliability, "_hard_quality_failure", lambda _draft: "")
    monkeypatch.setattr(
        refinement,
        "explicit_delivery_failure",
        lambda _prompt, _draft: "direct delivery is missing",
    )
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="test")

    verdict = asyncio.run(
        performance.verify_studio_scene_delivery_fast(config, STUDIO_MESSAGES, "tame draft")
    )

    assert verdict["verified"] is False
    assert verdict["requested_explicitness_delivered"] is False
    assert called is False


def test_llm_verifier_runs_only_after_deterministic_gates_pass(monkeypatch) -> None:
    called = False

    async def expensive_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True, "canon_respected": True}

    monkeypatch.setattr(performance, "_BASE_VERIFY", expensive_verify)
    monkeypatch.setattr(reliability, "_hard_quality_failure", lambda _draft: "")
    monkeypatch.setattr(refinement, "explicit_delivery_failure", lambda _prompt, _draft: "")
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="test")

    verdict = asyncio.run(
        performance.verify_studio_scene_delivery_fast(config, STUDIO_MESSAGES, "accepted draft")
    )

    assert verdict["verified"] is True
    assert called is True


def test_installed_verifier_prompt_limits_are_local_model_sized() -> None:
    assert streaming_generation._VERIFIER_CONTEXT_CHARS == 12000
    assert streaming_generation._VERIFIER_DRAFT_CHARS == 14000


def test_local_studio_uses_smaller_ollama_context_than_general_writer() -> None:
    studio_tokens = local_stream.ollama_context_tokens_for(
        local_stream._HERETIC_ROCINANTE,
        STUDIO_MESSAGES,
    )
    writer_tokens = local_stream.ollama_context_tokens_for(local_stream._HERETIC_ROCINANTE)

    assert studio_tokens == 16384
    assert writer_tokens > studio_tokens
