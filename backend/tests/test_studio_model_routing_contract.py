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
    assert "lock_model: true" in router
    assert "lock_model: false" in router


def test_studio_has_explicit_fast_and_quality_profiles() -> None:
    router = source("StudioModelRouter.tsx")

    assert "Quality 12B" in router
    assert "Fast 8B" in router
    assert "emberwriter.studioPerformanceProfile" in router
    assert "3,072-token" in router
    assert "4,096" in router


def test_known_local_models_have_clear_usage_guidance() -> None:
    router = source("StudioModelRouter.tsx")

    assert "qwen2.5-14b" in router
    assert "qwen3-8b" in router
    assert "mistral-small3.1" in router
    assert "Rocinante" in router
    assert "pygmalion-3-12b" in router
    assert "magnum-v4-12b" in router
    assert "Adult / roleplay specialist 12B" in router
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


def test_studio_uses_backend_measured_adult_model_recommendation() -> None:
    studio = source("AIStudioWorkspace.tsx")
    router = source("StudioModelRouter.tsx")

    assert "adult_model?: string | null" in studio
    assert "setAdultModelRecommendation(next.adult_model || '')" in studio
    assert "adultModelRecommendation={adultModelRecommendation}" in studio
    assert "adultModelRecommendation" in router
    assert "models.includes(adultModelRecommendation)" in router
