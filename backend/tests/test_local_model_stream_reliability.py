import asyncio

from app import generation, generation_reliability
from app import local_model_stream_reliability as reliability
from app.models import ProviderConfig

PYG = reliability._PYGMALION_ADULT
MAGNUM = reliability._MAGNUM_ADULT
ROCI = reliability._HERETIC_ROCINANTE
CYDONIA = reliability._HIGH_HEAT_CYDONIA
FAST = reliability._FAST_ADULT_MODEL


def _intimacy_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Scene intent: intimacy"},
        {"role": "user", "content": "Write the requested scene."},
    ]


def _studio_messages(chars: int = 2000) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Scene intent: intimacy\nSTUDIO SCENE DELIVERY CONTRACT:"},
        {"role": "user", "content": "x" * chars},
    ]


def test_heavy_model_uses_smaller_context_window() -> None:
    assert reliability.ollama_context_tokens_for(CYDONIA) == 16384
    assert reliability.ollama_context_tokens_for(ROCI) == generation.OLLAMA_CONTEXT_TOKENS


def test_studio_context_adapts_to_prompt_and_model_size() -> None:
    messages = _studio_messages()

    quality = reliability.ollama_context_tokens_for(ROCI, messages, max_output_tokens=4096)
    fast = reliability.ollama_context_tokens_for(FAST, messages, max_output_tokens=3072)

    assert quality == 10240
    assert fast == 8192
    assert fast < quality < generation.OLLAMA_CONTEXT_TOKENS


def test_large_studio_prompt_steps_up_context_without_returning_to_24k() -> None:
    messages = _studio_messages(chars=28000)

    quality = reliability.ollama_context_tokens_for(ROCI, messages, max_output_tokens=4096)
    fast = reliability.ollama_context_tokens_for(FAST, messages, max_output_tokens=3072)

    assert quality == 12288
    assert fast == 12288


def test_first_token_watchdog_is_longer_than_midstream_watchdog() -> None:
    assert reliability._FIRST_TOKEN_TIMEOUT_SECONDS == 15 * 60
    assert reliability._INTER_TOKEN_TIMEOUT_SECONDS == 5 * 60
    assert reliability._FIRST_TOKEN_TIMEOUT_SECONDS > reliability._INTER_TOKEN_TIMEOUT_SECONDS


def test_adult_routing_respects_valid_configured_12b_model(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [CYDONIA, FAST, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=ROCI)

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == ROCI


def test_adult_routing_respects_explicit_manual_model_lock(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [PYG, MAGNUM, FAST, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model=FAST,
        lock_model=True,
    )

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == FAST


def test_auto_adult_routing_prefers_dedicated_12b_candidate(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [PYG, MAGNUM, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    monkeypatch.setattr(reliability, "preferred_adult_model", lambda _installed: PYG)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=ROCI)

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == PYG


def test_auto_adult_routing_honors_measured_bakeoff_winner(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [PYG, MAGNUM, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    monkeypatch.setattr(reliability, "preferred_adult_model", lambda _installed: MAGNUM)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=ROCI)

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == MAGNUM


def test_stale_adult_model_repairs_to_dedicated_candidate_before_fast_or_24b(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [CYDONIA, FAST, ROCI, PYG]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    monkeypatch.setattr(reliability, "preferred_adult_model", lambda _installed: PYG)
    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="missing-writing-model:latest",
    )

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == PYG


def test_reliability_layer_replaces_low_level_transport_not_public_wrapper() -> None:
    assert generation_reliability._original_generate_streamed is reliability.generate_streamed_reliable
    assert generation_reliability._route_adult_model is reliability.route_adult_model_stable
