import asyncio
import json

from app import adult_specialist
from app.model_catalog import ADULT_EXPLICIT_MODEL
from app.models import ProviderConfig


def test_proven_specialist_contract_starts_at_explicit_scene_and_preserves_body_canon() -> None:
    context = """### Avery
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Avery has a penis. Avery does not have a vagina, vulva, or clitoris.

### Rowan
Rowan has a penis.

## Broad lore
A long unrelated history of kingdoms and politics.
"""
    messages = adult_specialist.build_adult_specialist_messages(
        "write",
        "Write the explicit sex scene between Rowan and Avery.",
        context,
        heat_level="inferno",
        delivery_scope="core_only",
        min_scene_words=900,
        scene_plan='{"opening_state":"Rowan stands; Avery sits.","beats":[{"objective":"advance"}]}',
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "adult-fiction scene specialist" in system
    assert "Begin the requested central sexual action in the first paragraph" in system
    assert "Do not stop to ask whether the characters are sure" in system
    assert "HARD BODY / EMBODIMENT CANON is literal author-owned fact" in system
    assert "HIDDEN SCENE DIRECTOR PLAN" in system
    assert "Rowan stands; Avery sits." in system
    assert "SILENT PHYSICAL STATE LEDGER" not in system
    assert "CONTINUITY FREEZE-FRAME" not in system
    assert "Avery has a penis" in user
    assert "Avery does not have a vagina, vulva, or clitoris" in user


def test_hidden_scene_director_infers_choreography_from_short_brief(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_generate(_config, messages, **kwargs) -> str:
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return json.dumps(
            {
                "opening_state": "Kaelen stands facing seated Muna.",
                "central_intent": "continuous encounter",
                "beats": [
                    {
                        "objective": "close distance",
                        "start_state": "standing / seated",
                        "transition": "Muna rises",
                        "action": "affectionate contact",
                        "end_state": "both standing",
                    },
                    {
                        "objective": "progress",
                        "start_state": "both standing",
                        "transition": "NONE",
                        "action": "continue encounter",
                        "end_state": "stable",
                    },
                ],
                "ending_goal": "resolution",
                "continuity_watchouts": ["do not invent anatomy"],
            }
        )

    monkeypatch.setattr(adult_specialist, "generate", fake_generate)
    config = ProviderConfig(provider="ollama", model="director-model")
    plan_text = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            config,
            "Kaelen and Muna in the changing room after the sauna. High heat. Communion deepens.",
            "### Muna\nHARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:\nMuna has a penis.\n",
            heat_level="inferno",
            delivery_scope="full_scene",
        )
    )

    plan = json.loads(plan_text)
    assert plan["opening_state"] == "Kaelen stands facing seated Muna."
    assert len(plan["beats"]) == 2
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "author should not have to choreograph the scene" in messages[0]["content"].lower()
    assert "Muna has a penis" in messages[1]["content"]
    assert captured["kwargs"]["json_mode"] is True


def test_adult_specialist_context_is_compact() -> None:
    broad = "UNRELATED_LORE " * 10000
    context = (
        "### Avery\nHARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:\n"
        "Avery has a penis. Avery does not have a vagina, vulva, or clitoris.\n\n"
        + broad
    )
    compact = adult_specialist.compact_adult_context(
        context,
        "Write an explicit scene between Avery and Rowan.",
    )
    assert len(compact) <= 18000
    assert "Avery has a penis" in compact


def test_explicit_request_detection_does_not_capture_ordinary_scene() -> None:
    assert adult_specialist.is_explicit_adult_request(
        "Write the battle scene.",
        "hot",
        "write",
    ) is False
    assert adult_specialist.is_explicit_adult_request(
        "Write the explicit sex scene.",
        "hot",
        "write",
    ) is True
    assert adult_specialist.is_explicit_adult_request(
        "Continue from here.",
        "inferno",
        "continue",
    ) is True


def test_local_explicit_request_routes_to_exact_proven_model(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [
            "hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M",
            ADULT_EXPLICIT_MODEL,
        ]

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M",
    )

    routed = asyncio.run(
        adult_specialist.route_explicit_adult_specialist(
            config,
            "Write the explicit sex scene.",
            "inferno",
            "write",
        )
    )

    assert routed is True
    assert config.model == ADULT_EXPLICIT_MODEL


def test_non_explicit_request_does_not_force_erotica_model(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [ADULT_EXPLICIT_MODEL]

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    config = ProviderConfig(provider="ollama", model="general-model")

    routed = asyncio.run(
        adult_specialist.route_explicit_adult_specialist(
            config,
            "Write the next action scene.",
            "hot",
            "write",
        )
    )

    assert routed is False
    assert config.model == "general-model"
