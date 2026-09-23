import asyncio
import json

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


def test_hidden_scene_director_infers_choreography_from_short_brief(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_generate(_config, messages, **kwargs) -> str:
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return json.dumps(
            {
                "opening_state": "Kaelen stands facing seated Muna.",
                "central_intent": "continuous encounter",
                "requested_acts": [],
                "character_engines": [
                    {
                        "character": "Muna",
                        "active_behavior": "turns play into initiative and rhythm",
                        "generic_shortcut_to_avoid": "constant giggling as a substitute for personality",
                    }
                ],
                "relationship_turn": "trust deepens through action rather than explanation",
                "magic_timing": "latter half",
                "beats": [
                    {
                        "objective": "close distance",
                        "start_state": "standing / seated",
                        "pose_geometry": {
                            "participant_a": "Kaelen standing facing Muna",
                            "participant_b": "Muna seated facing Kaelen",
                            "relative_position": "front",
                        },
                        "transition": "Muna rises",
                        "action": "affectionate contact",
                        "act_state": "NONE",
                        "actor": "Muna",
                        "receiver": "Kaelen",
                        "penetration_state": "NONE",
                        "mouth_state": "NONE",
                        "end_state": "both standing",
                    },
                    {
                        "objective": "progress",
                        "start_state": "both standing",
                        "pose_geometry": {
                            "participant_a": "Kaelen standing",
                            "participant_b": "Muna standing",
                            "relative_position": "front",
                        },
                        "transition": "NONE",
                        "action": "continue encounter",
                        "act_state": "NONE",
                        "actor": "Kaelen",
                        "receiver": "Muna",
                        "penetration_state": "NONE",
                        "mouth_state": "NONE",
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
    assert plan["character_engines"][0]["character"] == "Muna"
    assert plan["magic_timing"] == "latter half"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert "{POSITION_GEOMETRY_REFERENCE}" not in messages[0]["content"]
    assert "MISSIONARY / FACE-TO-FACE ANAL" in messages[0]["content"]
    assert "author should not have to choreograph the scene" in messages[0]["content"].lower()
    assert "make the encounter unmistakably specific to these characters" in messages[0]["content"].lower()
    assert "reserve its decisive realization for the latter half" in messages[0]["content"].lower()
    assert "named sexual act or position" in messages[0]["content"].lower()
    assert "do not merge incompatible requested acts" in messages[0]["content"].lower()
    assert "\"requested_acts\"" in messages[0]["content"]
    assert "\"actor\"" in messages[0]["content"]
    assert "\"receiver\"" in messages[0]["content"]
    assert "\"pose_geometry\"" in messages[0]["content"]
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


def test_hidden_scene_director_retries_when_named_acts_are_missing(monkeypatch) -> None:
    calls = 0
    captured: list[list[dict[str, str]]] = []

    def valid_plan() -> dict:
        return {
            "opening_state": "Kaelen stands facing seated Muna.",
            "central_intent": "continuous encounter",
            "requested_acts": [
                {
                    "request": "missionary",
                    "actor": "Kaelen",
                    "receiver": "Muna",
                    "canon_safe_interpretation": "face-to-face anal using established anatomy",
                    "required_geometry": "Muna on back; Kaelen in front between her legs",
                    "sequence_index": 1,
                },
                {
                    "request": "doggy style",
                    "actor": "Kaelen",
                    "receiver": "Muna",
                    "canon_safe_interpretation": "rear anal using established anatomy",
                    "required_geometry": "Muna facing away with hips raised; Kaelen behind",
                    "sequence_index": 2,
                },
                {
                    "request": "anal",
                    "actor": "Kaelen",
                    "receiver": "Muna",
                    "canon_safe_interpretation": "penis to anus",
                    "required_geometry": "pelvis aligned to anus",
                    "sequence_index": 3,
                },
                {
                    "request": "blowjob",
                    "actor": "Muna",
                    "receiver": "Kaelen",
                    "canon_safe_interpretation": "Muna mouth to Kaelen penis",
                    "required_geometry": "Muna mouth reachable to Kaelen penis",
                    "sequence_index": 4,
                },
            ],
            "character_engines": [],
            "relationship_turn": "trust deepens",
            "magic_timing": "latter half",
            "beats": [
                {
                    "objective": "missionary",
                    "start_state": "Muna seated",
                    "pose_geometry": {
                        "participant_a": "Muna on back",
                        "participant_b": "Kaelen in front",
                        "relative_position": "front between legs",
                    },
                    "transition": "Muna lies back",
                    "action": "missionary anal penetration",
                    "act_state": "missionary anal",
                    "actor": "Kaelen",
                    "receiver": "Muna",
                    "penetration_state": "Kaelen.penis -> Muna.anus",
                    "mouth_state": "NONE",
                    "end_state": "face-to-face",
                },
                {
                    "objective": "doggy",
                    "start_state": "face-to-face",
                    "pose_geometry": {
                        "participant_a": "Muna facing away hips raised",
                        "participant_b": "Kaelen kneeling behind",
                        "relative_position": "behind",
                    },
                    "transition": "withdraw and turn Muna onto hands and knees",
                    "action": "doggy style anal penetration",
                    "act_state": "doggy style anal",
                    "actor": "Kaelen",
                    "receiver": "Muna",
                    "penetration_state": "Kaelen.penis -> Muna.anus",
                    "mouth_state": "NONE",
                    "end_state": "rear",
                },
                {
                    "objective": "oral",
                    "start_state": "rear",
                    "pose_geometry": {
                        "participant_a": "Muna kneeling in front",
                        "participant_b": "Kaelen standing",
                        "relative_position": "front",
                    },
                    "transition": "Kaelen withdraws and Muna turns to face him",
                    "action": "blowjob oral sex",
                    "act_state": "blowjob",
                    "actor": "Muna",
                    "receiver": "Kaelen",
                    "penetration_state": "NONE",
                    "mouth_state": "Muna.mouth -> Kaelen.penis",
                    "end_state": "oral",
                },
            ],
            "ending_goal": "resolution",
            "continuity_watchouts": [],
        }

    async def fake_generate(_config, messages, **_kwargs) -> str:
        nonlocal calls
        captured.append(messages)
        calls += 1
        if calls == 1:
            bad = valid_plan()
            bad["requested_acts"] = []
            return json.dumps(bad)
        return json.dumps(valid_plan())

    monkeypatch.setattr(adult_specialist, "generate", fake_generate)
    plan_text = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            ProviderConfig(provider="ollama", model="director-model"),
            "Kaelen and Muna. missionary sex, doggy style sex, anal, blowjob.",
            "### Muna\nMuna has a penis.\n### Kaelen\nKaelen has a penis.",
            heat_level="inferno",
            delivery_scope="full_scene",
        )
    )

    assert calls == 2
    assert plan_text
    assert "PLANNER REPAIR REQUIREMENT" in captured[1][1]["content"]
    assert "plan omitted author-requested acts/positions" in captured[1][1]["content"]
    assert "DETECTED REQUIRED ACTS / POSITIONS: missionary, doggy, anal, blowjob" in captured[0][1]["content"]


def test_hidden_scene_director_prefers_dedicated_planning_model(monkeypatch) -> None:
    observed: dict[str, str] = {}

    async def installed(_base_url: str) -> list[str]:
        return [PLANNING_MODEL, ADULT_EXPLICIT_MODEL]

    async def fake_generate(config, _messages, **_kwargs) -> str:
        observed["model"] = config.model
        return json.dumps(
            {
                "opening_state": "A faces B.",
                "central_intent": "progress",
                "requested_acts": [],
                "character_engines": [],
                "relationship_turn": "closer",
                "magic_timing": "latter half",
                "beats": [
                    {"objective": "first change", "action": "move closer"},
                    {"objective": "second change", "action": "resolve"},
                ],
                "ending_goal": "resolution",
                "continuity_watchouts": [],
            }
        )

    monkeypatch.setattr(adult_specialist, "installed_ollama_models", installed)
    monkeypatch.setattr(adult_specialist, "generate", fake_generate)

    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model=ADULT_EXPLICIT_MODEL,
    )
    plan = asyncio.run(
        adult_specialist.build_hidden_adult_scene_plan(
            config,
            "Write a high-heat scene between A and B.",
            "Adult characters.",
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
