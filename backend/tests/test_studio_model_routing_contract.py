from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def source(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_studio_exposes_task_aware_model_router() -> None:
    studio = source("AIStudioWorkspace.tsx")
    router = source("StudioModelRouter.tsx")

    assert "StudioModelRouter" in studio
    assert "heatLevel={craft.heat_level}" in studio
    assert "prompt={prompt}" in studio
    assert "Auto-match my writing" in router
    assert "Adult / high heat" in router
    assert "General fiction" in router
    assert "Character & dialogue" in router
    assert "Plotting & analysis" in router


def test_auto_routing_detects_high_heat_and_brainstorming() -> None:
    router = source("StudioModelRouter.tsx")

    assert "heat === 'scorching' || heat === 'inferno'" in router
    assert "ADULT_PROMPT.test(prompt)" in router
    assert "mode === 'brainstorm'" in router
    assert "return 'planning'" in router
    assert "return 'adult'" in router


def test_manual_model_choice_disables_auto_switching_until_reenabled() -> None:
    router = source("StudioModelRouter.tsx")

    assert "setAutoSwitch(false)" in router
    assert "setAutoSwitch(true)" in router
    assert "Manual override locked" in router
    assert "Auto-switch within this profile" in router


def test_studio_has_explicit_fast_and_quality_profiles() -> None:
    router = source("StudioModelRouter.tsx")

    assert ">Quality</button>" in router
    assert ">Fast</button>" in router
    assert "emberwriter.studioPerformanceProfile" in router
    assert "3,072-token" in router
    assert "regardless of parameter count" in router
    assert "4,096" in router


def test_known_local_models_have_clear_usage_guidance() -> None:
    router = source("StudioModelRouter.tsx")

    assert "qwen2.5-14b" in router
    assert "qwen3-8b" in router
    assert "mistral-small3.1" in router
    assert "Rocinante" in router
    assert "qwen3.5-4b-nsfw-ara-heretic-literotica" in router
    assert "pygmalion-3" in router
    assert "magnum-v4" in router
    assert "Apache-2.0" in router
    assert "Installed model guide" in router
    assert "Best installed fallback" in router


def test_model_refresh_no_longer_blindly_selects_first_model() -> None:
    studio = source("AIStudioWorkspace.tsx")

    assert "setModels(next.models)" in studio
    assert "next.models[0]" not in studio


def test_studio_exposes_core_only_scope_without_removing_complete_scene_mode() -> None:
    studio = source("AIStudioWorkspace.tsx")
    assert "Complete scene" in studio
    assert "Core only" in studio
    assert "CORE_ONLY_INTENT" in studio
    assert "I will write everything else" not in studio  # regex handles contractions/spacing generically
    assert "delivery_scope: scope" in studio


def test_adult_router_uses_persisted_acceptance_winner() -> None:
    studio = source("AIStudioWorkspace.tsx")
    router = source("StudioModelRouter.tsx")

    assert "preferences={modelPreferences}" in studio
    assert "adult_explicit_model" in router
    assert "Dedicated adult-explicit capability model" in router


def test_quality_adult_routing_can_select_fast_model_when_it_wins_bakeoff() -> None:
    router = source("StudioModelRouter.tsx")
    assert "acceptedAdult && name === acceptedAdult" in router
    assert "qwen3Heretic8" in router
    assert "trusts the local bakeoff over the model label" in router


def test_selector_has_dedicated_capability_preferences() -> None:
    router = source("StudioModelRouter.tsx")
    assert "preferences.adult_explicit_model" in router
    assert "preferences.general_prose_model" in router
    assert "preferences.character_model" in router
    assert "preferences.planning_model" in router
    assert "Proven adult-explicit specialist 4B" in router
    assert "General prose specialist 12B" in router
    assert "Character / roleplay specialist 12B" in router


def test_erotica_specialist_is_penalized_for_non_adult_work() -> None:
    router = source("StudioModelRouter.tsx")
    assert "else if (literotica4) score -= 80" in router
    assert "else if (literotica4) score -= 50" in router
    assert "else if (literotica4) score -= 90" in router
