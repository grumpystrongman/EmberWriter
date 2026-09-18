import asyncio

import app.generation_reliability as reliability
import app.generation_reliability_refinement as refinement
import app.local_model_stream_reliability as local_stream
import app.studio_local_performance as performance
from app import streaming_generation
from app.models import ProviderConfig

STUDIO_MESSAGES = [
    {"role": "system", "content": "Scene intent: intimacy\nSTUDIO SCENE DELIVERY CONTRACT:"},
    {"role": "user", "content": "AUTHOR INSTRUCTION\nWrite the requested scene."},
]


async def _noop_delta(_text: str) -> None:
    return None


def _run_budgeted(monkeypatch, model: str) -> tuple[dict[str, int], list[str]]:
    observed: dict[str, int] = {}
    statuses: list[str] = []

    async def fake_base(*_args, **kwargs) -> str:
        observed["max_passes"] = kwargs["max_passes"]
        observed["max_output_tokens"] = kwargs["max_output_tokens"]
        return "draft"

    async def status(message: str) -> None:
        statuses.append(message)

    monkeypatch.setattr(performance, "_BASE_STREAMED_COMPLETE", fake_base)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=model)
    result = asyncio.run(
        performance.generate_complete_prose_streamed_budgeted(
            config,
            STUDIO_MESSAGES,
            min_words=300,
            on_delta=_noop_delta,
            on_status=status,
            max_passes=6,
            max_output_tokens=6144,
        )
    )
    assert result == "draft"
    return observed, statuses


def test_quality_local_studio_caps_generation_work(monkeypatch) -> None:
    observed, statuses = _run_budgeted(monkeypatch, local_stream._HERETIC_ROCINANTE)

    assert observed["max_passes"] == 2
    assert observed["max_output_tokens"] == 4096
    assert any("Quality 12B" in message for message in statuses)
    assert any("compact semantic verifier" in message for message in statuses)


def test_fast_local_studio_uses_tighter_output_budget(monkeypatch) -> None:
    observed, statuses = _run_budgeted(monkeypatch, local_stream._FAST_ADULT_MODEL)

    assert observed["max_passes"] == 2
    assert observed["max_output_tokens"] == 3072
    assert any("Fast 8B" in message for message in statuses)


def test_nonlocal_generation_keeps_caller_budget(monkeypatch) -> None:
    observed: dict[str, int] = {}

    async def fake_base(*_args, **kwargs) -> str:
        observed["max_passes"] = kwargs["max_passes"]
        observed["max_output_tokens"] = kwargs["max_output_tokens"]
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
            max_output_tokens=6144,
        )
    )

    assert observed["max_passes"] == 6
    assert observed["max_output_tokens"] == 6144


def test_prompt_echo_is_rejected_before_explicitness_scoring(monkeypatch) -> None:
    called = False

    async def expensive_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True}

    def explicitness_should_not_run(_prompt: str, _draft: str) -> str:
        raise AssertionError("explicitness scoring must not inspect assistant/prompt-echo prose")

    monkeypatch.setattr(performance, "_verify_local_studio_scene_delivery", expensive_verify)
    monkeypatch.setattr(refinement, "explicit_delivery_failure", explicitness_should_not_run)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="test")

    verdict = asyncio.run(
        performance.verify_studio_scene_delivery_fast(
            config,
            STUDIO_MESSAGES,
            "[EMBER_PROMPT]I understand the parameters. Here is my continuation.",
        )
    )

    assert verdict["verified"] is False
    assert "non-manuscript assistant/meta response" in str(verdict["reason"])
    assert called is False


def test_deterministic_explicitness_failure_skips_semantic_verifier(monkeypatch) -> None:
    called = False

    async def expensive_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True}

    monkeypatch.setattr(performance, "_verify_local_studio_scene_delivery", expensive_verify)
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


def test_local_studio_runs_compact_semantic_verifier_after_deterministic_gates(monkeypatch) -> None:
    called = False

    async def compact_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True, "canon_respected": True}

    monkeypatch.setattr(performance, "_verify_local_studio_scene_delivery", compact_verify)
    monkeypatch.setattr(reliability, "_hard_quality_failure", lambda _draft: "")
    monkeypatch.setattr(refinement, "explicit_delivery_failure", lambda _prompt, _draft: "")
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="test")

    verdict = asyncio.run(
        performance.verify_studio_scene_delivery_fast(config, STUDIO_MESSAGES, "accepted draft")
    )

    assert verdict["verified"] is True
    assert called is True


def test_nonlocal_generation_keeps_base_llm_verifier(monkeypatch) -> None:
    called = False

    async def expensive_verify(*_args, **_kwargs):
        nonlocal called
        called = True
        return {"verified": True, "canon_respected": True}

    monkeypatch.setattr(performance, "_BASE_VERIFY", expensive_verify)
    monkeypatch.setattr(reliability, "_hard_quality_failure", lambda _draft: "")
    monkeypatch.setattr(refinement, "explicit_delivery_failure", lambda _prompt, _draft: "")
    config = ProviderConfig(
        provider="openai_compatible",
        base_url="http://example.test/v1",
        model="test",
    )

    verdict = asyncio.run(
        performance.verify_studio_scene_delivery_fast(config, STUDIO_MESSAGES, "accepted draft")
    )

    assert verdict["verified"] is True
    assert called is True


def test_compact_verifier_budget_is_smaller_than_quality_prose_context() -> None:
    quality_context = local_stream.ollama_context_tokens_for(
        local_stream._HERETIC_ROCINANTE,
        STUDIO_MESSAGES,
        max_output_tokens=4096,
    )

    assert performance._LOCAL_VERIFIER_CONTEXT_TOKENS == 8192
    assert performance._LOCAL_VERIFIER_OUTPUT_TOKENS == 220
    assert performance._LOCAL_VERIFIER_CONTEXT_TOKENS < quality_context


def test_installed_verifier_prompt_limits_are_local_model_sized() -> None:
    assert streaming_generation._VERIFIER_CONTEXT_CHARS == 12000
    assert streaming_generation._VERIFIER_DRAFT_CHARS == 14000


def test_local_studio_uses_smaller_ollama_context_than_general_writer() -> None:
    studio_tokens = local_stream.ollama_context_tokens_for(
        local_stream._HERETIC_ROCINANTE,
        STUDIO_MESSAGES,
        max_output_tokens=4096,
    )
    writer_tokens = local_stream.ollama_context_tokens_for(local_stream._HERETIC_ROCINANTE)

    assert studio_tokens == 10240
    assert writer_tokens > studio_tokens
