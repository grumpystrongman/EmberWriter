import asyncio

import pytest

from app import explicit_delivery_policy as policy
from app import generation_reliability as reliability
from app import generation_reliability_refinement as refinement
from app import model_provisioning
from app.models import ProviderConfig


def test_standard_rocinante_is_not_treated_as_explicit_capable() -> None:
    standard = "HammerAI/rocinante-v1.1:12b-q4_K_M"
    heretic = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"

    assert policy.is_decensored_creative_model(standard) is False
    assert policy.is_decensored_creative_model(heretic) is True
    assert policy.has_explicit_creative_model([standard]) is False
    assert policy.has_explicit_creative_model([standard, heretic]) is True
    assert policy.explicit_creative_model_score(heretic) > policy.explicit_creative_model_score(standard)
    assert model_provisioning.BASELINE_CREATIVE_MODEL == heretic


def test_pg13_euphemistic_scene_fails_strict_explicit_gate() -> None:
    prompt = (
        "Write an explicit sex scene between consenting adults with penetration, genitalia, "
        "and both participants having an orgasm."
    )
    pg13 = (
        "They undressed and kissed until the room felt impossibly warm. "
        "He guided her to the bench and breached her fully, their bodies moving in a steady rhythm. "
        "Skin met skin as their connection deepened and they reached a shared climax together. "
        "Afterward they held each other, breathless and smiling."
    )

    reason = policy.strict_explicit_delivery_failure(prompt, pg13)
    assert reason
    assert "anatom" in reason.casefold() or "explicit" in reason.casefold()


def test_direct_anatomy_action_and_release_can_pass_strict_gate() -> None:
    prompt = "Write an explicit consenting-adult sex scene with genitalia and orgasm."
    direct = (
        "The adult partners named the boundary and consented clearly.\n\n"
        "He touched her clitoris, then penetrated her vagina while she guided the pace. "
        "They kept communicating as he thrust, and she came first.\n\n"
        "He orgasmed afterward, and they stopped to check in and rest together."
    )

    assert policy.strict_explicit_delivery_failure(prompt, direct) == ""


def test_quality_pass_cannot_sanitize_explicit_delivery(monkeypatch) -> None:
    original = (
        "The consenting adult partners stayed together.\n\n"
        "He touched her clitoris and penetrated her vagina while she guided him. "
        "She came, then he orgasmed."
    )
    sanitized = (
        "They undressed, kissed, and became one in a private moment. "
        "Their bodies moved together until they reached a shared climax."
    )

    async def fake_base(*args, **kwargs):
        return sanitized

    monkeypatch.setattr(policy, "_base_quality_pass", fake_base)
    result = asyncio.run(
        policy.strict_quality_pass(
            ProviderConfig(model="test-model"),
            draft=original,
            author_prompt="Write an explicit sex scene with genitalia and orgasm.",
            craft_context="Requested heat: inferno.",
        )
    )
    assert result == original


def test_inferno_model_routing_refuses_tame_creative_fallback(monkeypatch) -> None:
    async def fake_installed(_base_url: str) -> list[str]:
        return ["HammerAI/rocinante-v1.1:12b-q4_K_M"]

    monkeypatch.setattr(policy.ollama_runtime, "installed_ollama_models", fake_installed)
    config = ProviderConfig(provider="ollama", model="HammerAI/rocinante-v1.1:12b-q4_K_M")
    messages = [
        {"role": "system", "content": "Scene intent: intimacy\nRequested heat: inferno."},
        {"role": "user", "content": "AUTHOR INSTRUCTION\nWrite an explicit adult scene."},
    ]

    with pytest.raises(RuntimeError, match="No decensored creative writing model"):
        asyncio.run(policy.strict_route_adult_model(config, messages))


def test_installed_heretic_model_is_forced_for_intimacy(monkeypatch) -> None:
    standard = "HammerAI/rocinante-v1.1:12b-q4_K_M"
    heretic = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"

    async def fake_installed(_base_url: str) -> list[str]:
        return [standard, heretic]

    monkeypatch.setattr(policy.ollama_runtime, "installed_ollama_models", fake_installed)
    config = ProviderConfig(provider="ollama", model=standard)
    messages = [
        {"role": "system", "content": "Scene intent: intimacy\nRequested heat: inferno."},
        {"role": "user", "content": "AUTHOR INSTRUCTION\nWrite an explicit adult scene."},
    ]

    asyncio.run(policy.strict_route_adult_model(config, messages))
    assert config.model == heretic
    assert reliability.adult_model_score(heretic) > reliability.adult_model_score(standard)
    assert refinement.explicit_delivery_failure is policy.strict_explicit_delivery_failure
