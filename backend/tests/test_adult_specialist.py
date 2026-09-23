import asyncio
import json

import pytest

from app import adult_specialist
from app.model_catalog import ADULT_EXPLICIT_MODEL, PLANNING_MODEL
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
    assert "execute each meaningful beat once, in order" in system
    assert "requested_acts" in system
    assert "POSITION GEOMETRY REFERENCE" in system
    assert "MISSIONARY / FACE-TO-FACE ANAL" in system
    assert "DOGGY STYLE / REAR ANAL" in system
    assert "BLOWJOB / ORAL ON PENIS" in system
    assert "A position name is not a new organ" in system
    assert "One occupied body part cannot perform two incompatible jobs at once" in system
    assert "slick entrance" in system
    assert "do not reduce a character to one repeated tic" in system.lower()
    assert "do not resolve or explain it before the director's planned timing" in system.lower()
    assert "SILENT PHYSICAL STATE LEDGER" not in system
    assert "CONTINUITY FREEZE-FRAME" not in system
    assert "Avery has a penis" in user
    assert "Avery does not have a vagina, vulva, or clitoris" in user



def test_hidden_scene_director_builds_physical_skeleton_before_optional_enrichment(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def installed(_base_url: str) -> list[str]:
        return [PLANNING_MODEL]

    async def fake_generate(config, messages, **kwargs) -> str:
        captured["model"] = config.model
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return json.dumps(
            {
                "character_engines": [
                    {
                        "character": "Muna",
                        "active_behavior": "turns play into deliberate initiative and rhythm",
                        "generic_shortcut_to_avoid": "constant laughter as a substitute for personality",
                    },
                    {
                        "character": "Kaelen",
                        "active_behavior": "responds attentively to Muna's choices",
                        "generic_shortcut_to_avoid": "generic dominance",
                    },
                ],
                "relationship_turn": "trust deepens through responsive action",
                "magic_timing": "latter half",
                "ending_goal": "physical resolution with an immediate Communion shift",
                "beat_notes": [
                    {
                        "beat_index": 1,
                        "character_expression": "Muna controls the opening rhythm playfully.",
                        "novelty": "Muna turns the author-specified seated/standing geometry into initiative.",
                        "do_not_repeat": "introductory kissing",
                    }
                ],
            }
        )

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    prompt = """Write a high-heat sex scene between Kaelen and Muna.
Location: private gym changing area after a sauna.
Starting situation: Muna is seated on the mat and Kaelen is standing in front of her.
Tone: playful, physical, joyful, explicit, missionary sex, doggy style sex, anal, blowjob
Outcome: deepen their connection and intimacy.
Let the encounter develop naturally from their personalities."""
    context = """### Muna
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Muna has a penis. Muna does not have a vagina, vulva, or clitoris.

### Kaelen
HARD BODY / EMBODIMENT CANON — AUTHOR-OWNED; USE EXACTLY:
Kaelen has a penis.
"""
    plan_text = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="writer"),
            prompt,
            context,
            heat_level="inferno",
            delivery_scope="core_only",
        )
    )

    plan = json.loads(plan_text)
    assert plan["planning_source"] == "deterministic_physical_skeleton+model_enrichment"
    assert [item["request"] for item in plan["requested_acts"]] == [
        "missionary",
        "doggy style",
        "anal",
        "blowjob",
    ]
    assert len(plan["beats"]) == 3
    assert plan["beats"][0]["act_state"] == "blowjob"
    assert plan["beats"][0]["actor"] == "Muna"
    assert plan["beats"][0]["receiver"] == "Kaelen"
    assert plan["beats"][0]["mouth_state"] == "Muna.mouth -> Kaelen.penis"
    assert plan["beats"][1]["act_state"] == "missionary anal"
    assert plan["beats"][1]["penetration_state"] == "Kaelen.penis -> Muna.anus"
    assert plan["beats"][2]["act_state"] == "doggy style anal"
    assert plan["beats"][2]["penetration_state"] == "Kaelen.penis -> Muna.anus"
    assert plan["beats"][1]["transition"] != "NONE"
    assert plan["beats"][2]["transition"] != "NONE"
    assert plan["character_engines"][0]["character"] == "Muna"
    assert captured["model"] == PLANNING_MODEL
    assert captured["kwargs"]["json_mode"] is True
    assert captured["kwargs"]["max_output_tokens"] == 800
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "DO NOT CHANGE ACT ORDER, OWNERSHIP, ANATOMY, OR GEOMETRY" in messages[1]["content"]
    assert len(messages[1]["content"]) < 16000

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



def test_planner_repeat_limit_does_not_block_deterministic_scene_plan(monkeypatch) -> None:
    async def installed(_base_url: str) -> list[str]:
        return [PLANNING_MODEL]

    async def fake_generate(_config, _messages, **_kwargs) -> str:
        raise RuntimeError("Ollama could not generate: prediction aborted, token repeat limit reached")

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    prompt = """Write a high-heat sex scene between Kaelen and Muna.
Starting situation: Muna is seated on the mat and Kaelen is standing in front of her.
Tone: explicit, missionary sex, doggy style sex, anal, blowjob"""
    plan_text = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            ProviderConfig(provider="ollama", base_url="http://localhost:11434", model="writer"),
            prompt,
            "### Muna\nMuna has a penis.\n### Kaelen\nKaelen has a penis.",
            heat_level="inferno",
            delivery_scope="core_only",
        )
    )

    plan = json.loads(plan_text)
    assert plan["planning_source"] == "deterministic_physical_skeleton"
    assert "token repeat limit reached" in plan["enrichment_status"]
    assert len(plan["beats"]) == 3
    assert adult_specialist._scene_plan_failure(plan, prompt, "core_only") == ""


def test_hidden_scene_enrichment_prefers_dedicated_planning_model(monkeypatch) -> None:
    observed: dict[str, str] = {}

    async def installed(_base_url: str) -> list[str]:
        return [PLANNING_MODEL, ADULT_EXPLICIT_MODEL]

    async def fake_generate(config, _messages, **_kwargs) -> str:
        observed["model"] = config.model
        return json.dumps({"relationship_turn": "closer through action"})

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    plan = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            ProviderConfig(
                provider="ollama",
                base_url="http://localhost:11434",
                model=ADULT_EXPLICIT_MODEL,
            ),
            "Write a high-heat scene between A and B. missionary sex, anal.",
            "### A\nA has a penis.\n### B\nB has a penis.",
            heat_level="inferno",
            delivery_scope="full_scene",
        )
    )

    assert plan
    assert observed["model"] == PLANNING_MODEL

def test_scene_plan_accepts_anal_covered_inside_position_entries() -> None:
    prompt = "missionary sex, doggy style sex, anal, blowjob"
    plan = {
        "requested_acts": [
            {
                "request": "missionary",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "missionary anal",
                "required_geometry": "B on back; A in front",
            },
            {
                "request": "doggy style",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "rear anal",
                "required_geometry": "B facing away; A behind",
            },
            {
                "request": "blowjob",
                "actor": "B",
                "receiver": "A",
                "canon_safe_interpretation": "oral on penis",
                "required_geometry": "B in front of A",
            },
        ],
        "beats": [
            {
                "objective": "missionary anal",
                "action": "missionary anal penetration",
                "act_state": "missionary anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "front"},
            },
            {
                "objective": "doggy style anal",
                "action": "doggy style anal penetration",
                "act_state": "doggy style anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "behind"},
            },
            {
                "objective": "blowjob",
                "action": "blowjob oral sex",
                "act_state": "blowjob",
                "actor": "B",
                "receiver": "A",
                "pose_geometry": {"relative_position": "front"},
            },
        ],
    }

    assert adult_specialist._scene_plan_failure(plan, prompt) == ""


def test_scene_plan_allows_non_requested_transition_beats_without_full_geometry() -> None:
    prompt = "missionary sex"
    plan = {
        "requested_acts": [
            {
                "request": "missionary",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "face-to-face anal",
                "required_geometry": "B on back; A in front",
            }
        ],
        "beats": [
            {
                "objective": "character-specific transition",
                "action": "brief emotional transition",
            },
            {
                "objective": "missionary",
                "action": "missionary anal penetration",
                "act_state": "missionary",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "front"},
            },
        ],
    }

    assert adult_specialist._scene_plan_failure(plan, prompt) == ""



def test_model_enrichment_cannot_replace_fixed_physical_beats(monkeypatch) -> None:
    async def fake_generate(_config, _messages, **_kwargs) -> str:
        return json.dumps(
            {
                "relationship_turn": "closer",
                "beats": [
                    {
                        "objective": "bad collapsed beat",
                        "action": "ignore all requested positions",
                    }
                ],
                "requested_acts": [],
                "beat_notes": [
                    {
                        "beat_index": 2,
                        "character_expression": "Kaelen follows Muna's rhythm.",
                        "novelty": "face-to-face configuration changes the dynamic",
                        "do_not_repeat": "oral beat",
                    }
                ],
            }
        )

    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    prompt = "Write a sex scene between Kaelen and Muna. missionary sex, doggy style sex, anal, blowjob."
    plan = json.loads(
        asyncio.run(
            adult_specialist.build_hidden_adult_scene_plan(
                ProviderConfig(provider="openai_compatible", model="planner"),
                prompt,
                "### Muna\nMuna has a penis.\n### Kaelen\nKaelen has a penis.",
                heat_level="inferno",
                delivery_scope="core_only",
            )
        )
    )

    assert len(plan["requested_acts"]) == 4
    assert len(plan["beats"]) == 3
    assert plan["beats"][0]["act_state"] == "missionary anal"
    assert plan["beats"][1]["act_state"] == "doggy style anal"
    assert plan["beats"][2]["act_state"] == "blowjob"
    assert plan["beats"][1]["character_expression"] == "Kaelen follows Muna's rhythm."
    assert adult_specialist._scene_plan_failure(plan, prompt, "core_only") == ""


def test_unreadable_enrichment_json_keeps_valid_deterministic_plan(monkeypatch) -> None:
    async def fake_generate(_config, _messages, **_kwargs) -> str:
        return "{not valid json"

    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    prompt = "Write a sex scene between Kaelen and Muna. missionary sex, doggy style sex, anal, blowjob."
    plan = json.loads(
        asyncio.run(
            adult_specialist.build_hidden_adult_scene_plan(
                ProviderConfig(provider="openai_compatible", model="planner"),
                prompt,
                "### Muna\nMuna has a penis.\n### Kaelen\nKaelen has a penis.",
                heat_level="inferno",
                delivery_scope="full_scene",
            )
        )
    )

    assert plan["planning_source"] == "deterministic_physical_skeleton"
    assert "unreadable enrichment JSON" in plan["enrichment_status"]
    assert adult_specialist._scene_plan_failure(plan, prompt, "full_scene") == ""

def test_core_only_plan_requires_first_beat_to_deliver_requested_act() -> None:
    prompt = "missionary sex, doggy style sex, anal, blowjob"
    plan = {
        "requested_acts": [
            {
                "request": "missionary",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "missionary anal",
                "required_geometry": "B on back; A in front",
            },
            {
                "request": "doggy style",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "doggy style anal",
                "required_geometry": "B facing away; A behind",
            },
            {
                "request": "blowjob",
                "actor": "B",
                "receiver": "A",
                "canon_safe_interpretation": "oral sex on penis",
                "required_geometry": "B mouth reachable to A penis",
            },
        ],
        "beats": [
            {
                "objective": "teasing setup",
                "action": "kiss and tease before anything requested",
            },
            {
                "objective": "missionary anal",
                "action": "missionary anal penetration",
                "act_state": "missionary anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "front"},
            },
            {
                "objective": "doggy style anal",
                "action": "doggy style anal penetration",
                "act_state": "doggy style anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "behind"},
            },
            {
                "objective": "blowjob",
                "action": "blowjob oral sex",
                "act_state": "blowjob",
                "actor": "B",
                "receiver": "A",
                "pose_geometry": {"relative_position": "front"},
            },
        ],
    }

    reason = adult_specialist._scene_plan_failure(plan, prompt, "core_only")
    assert "beat 1 must directly deliver" in reason


def test_core_only_plan_accepts_requested_act_in_first_beat() -> None:
    prompt = "missionary sex, doggy style sex, anal, blowjob"
    plan = {
        "requested_acts": [
            {
                "request": "missionary",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "missionary anal",
                "required_geometry": "B on back; A in front",
            },
            {
                "request": "doggy style",
                "actor": "A",
                "receiver": "B",
                "canon_safe_interpretation": "doggy style anal",
                "required_geometry": "B facing away; A behind",
            },
            {
                "request": "blowjob",
                "actor": "B",
                "receiver": "A",
                "canon_safe_interpretation": "oral sex on penis",
                "required_geometry": "B mouth reachable to A penis",
            },
        ],
        "beats": [
            {
                "objective": "missionary anal",
                "action": "missionary anal penetration",
                "act_state": "missionary anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "front"},
            },
            {
                "objective": "doggy style anal",
                "action": "doggy style anal penetration",
                "act_state": "doggy style anal",
                "actor": "A",
                "receiver": "B",
                "pose_geometry": {"relative_position": "behind"},
            },
            {
                "objective": "blowjob",
                "action": "blowjob oral sex",
                "act_state": "blowjob",
                "actor": "B",
                "receiver": "A",
                "pose_geometry": {"relative_position": "front"},
            },
        ],
    }

    assert adult_specialist._scene_plan_failure(plan, prompt, "core_only") == ""
