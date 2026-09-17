import asyncio

from app import generation, generation_reliability
from app import local_model_stream_reliability as reliability
from app.models import ProviderConfig

ROCI = reliability._HERETIC_ROCINANTE
CYDONIA = reliability._HIGH_HEAT_CYDONIA


def _intimacy_messages() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Scene intent: intimacy"},
        {"role": "user", "content": "Write the requested scene."},
    ]


def test_heavy_model_uses_smaller_context_window() -> None:
    assert reliability.ollama_context_tokens_for(CYDONIA) == 16384
    assert reliability.ollama_context_tokens_for(ROCI) == generation.OLLAMA_CONTEXT_TOKENS


def test_first_token_watchdog_is_longer_than_midstream_watchdog() -> None:
    assert reliability._FIRST_TOKEN_TIMEOUT_SECONDS == 15 * 60
    assert reliability._INTER_TOKEN_TIMEOUT_SECONDS == 5 * 60
    assert reliability._FIRST_TOKEN_TIMEOUT_SECONDS > reliability._INTER_TOKEN_TIMEOUT_SECONDS


def test_adult_routing_respects_valid_configured_12b_model(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [CYDONIA, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    config = ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=ROCI)

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == ROCI


def test_stale_adult_model_repairs_to_12b_before_24b(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [CYDONIA, ROCI]

    monkeypatch.setattr(reliability, "installed_ollama_models", installed)
    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="missing-writing-model:latest",
    )

    asyncio.run(reliability.route_adult_model_stable(config, _intimacy_messages()))

    assert config.model == ROCI


def test_reliability_layer_replaces_low_level_transport_not_public_wrapper() -> None:
    assert generation_reliability._original_generate_streamed is reliability.generate_streamed_reliable
    assert generation_reliability._route_adult_model is reliability.route_adult_model_stable
