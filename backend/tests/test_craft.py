import asyncio
from pathlib import Path

from app import craft, storage, story_intelligence, style_fidelity
from app.models import CraftControls, CraftProfile, ProviderConfig, VoiceProfile


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_craft_profile_and_voice_lock_round_trip(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Craft Test")
    slug = project["slug"]

    profile = CraftProfile(
        default_heat="scorching",
        default_tension_curve="pressure_cooker",
        quality_pass_default=True,
        prose_directive="Close POV, sharp verbs, earned vulnerability.",
        avoidances=["generic banter", "purple euphemism"],
    )
    craft.save_craft_profile(slug, profile)
    craft.save_voice_profile(
        slug,
        VoiceProfile(
            name="Nexus voice",
            prose_directive="Tight third-person with tactile imagery and dry humor.",
            sentence_rhythm="Long pressure-building lines broken by short decisive sentences.",
            diction="Concrete and contemporary.",
            imagery="Elemental images tied to the magic system.",
            dialogue="Character-specific, clipped under stress.",
            interiority="Embodied and immediate.",
            pov_distance="Close third.",
            sensual_voice="Anticipation and emotional risk precede direct physical detail.",
            signature_traits=["physicalized emotion"],
            avoidances=["interchangeable reactions"],
        ),
    )
    style_fidelity.save_style_fidelity(
        slug,
        {
            "metrics": {"avg_sentence_words": 11.5, "dialogue_ratio": 0.31},
            "human_irregularities": ["Keep blunt fragments under pressure."],
            "anti_ai_rules": ["Do not restate the emotion after showing it."],
            "dialogue_rules": ["Let interruptions carry tension."],
            "interiority_rules": ["Filter emotion through physical perception."],
            "author_notes": "Rough edges are intentional.",
        },
    )

    loaded = craft.get_craft_profile(slug)
    assert loaded.default_heat == "scorching"
    assert loaded.default_tension_curve == "pressure_cooker"

    context, files = craft.build_craft_context(
        slug,
        CraftControls(
            heat_level="inferno",
            tension_curve="slow_burn",
            voice_lock=True,
            sensory_intensity=4,
            dialogue_intensity=2,
            interiority=5,
        ),
    )
    assert "maximum on-page explicitness" in context
    assert "Nexus voice" in context
    assert "physicalized emotion" in context
    assert "Do not restate the emotion" in context
    assert "Rough edges are intentional" in context
    assert craft.CRAFT_PROFILE_PATH in files
    assert craft.VOICE_PROFILE_PATH in files
    assert style_fidelity.STYLE_FIDELITY_PATH in files


def test_voice_lab_saves_structured_profile(tmp_path: Path, monkeypatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Voice Test")
    slug = project["slug"]

    async def fake_generate(*args, **kwargs):
        return """{
          "name": "Learned voice",
          "prose_directive": "Close, vivid, unsentimental.",
          "sentence_rhythm": "Mixed cadence.",
          "diction": "Concrete.",
          "imagery": "Sparse elemental imagery.",
          "dialogue": "Dry and character-specific.",
          "interiority": "Embodied.",
          "pov_distance": "Close third.",
          "sensual_voice": "Tension before release.",
          "signature_traits": ["compressed emotional turns"],
          "avoidances": ["generic phrasing"]
        }"""

    monkeypatch.setattr(craft, "generate", fake_generate)
    provider = ProviderConfig(model="test-model")
    sample = "A" * 400
    profile = asyncio.run(craft.analyze_voice(slug, sample, provider, "Learned voice"))

    assert profile.name == "Learned voice"
    assert profile.sensual_voice == "Tension before release."
    saved = craft.get_voice_profile(slug)
    assert saved is not None
    assert saved.signature_traits == ["compressed emotional turns"]


def test_style_fidelity_measurement_and_round_trip(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Style Fidelity Test")
    slug = project["slug"]
    sample = (
        '"You came back?" Mara asked.\n\n'
        'He nodded. Too late.\n\n'
        'She laughed once—sharp, unbelieving—and looked toward the door. '
        'There were ten things she could have said; none of them survived the silence.'
    )
    saved = style_fidelity.build_style_fidelity_from_sample(
        slug,
        sample,
        {
            "human_irregularities": ["Keep clipped fragments in tense scenes."],
            "anti_ai_rules": ["No symmetrical summary paragraphs."],
            "dialogue_rules": ["Dialogue may trail into action."],
            "interiority_rules": ["Use implication before explanation."],
        },
    )
    assert saved["metrics"]["avg_sentence_words"] > 0
    assert saved["metrics"]["dialogue_ratio"] > 0
    loaded = style_fidelity.get_style_fidelity(slug)
    assert loaded is not None
    assert loaded["anti_ai_rules"] == ["No symmetrical summary paragraphs."]
    context = style_fidelity.build_style_fidelity_context(slug)
    assert "Keep clipped fragments" in context
    assert "Dialogue may trail" in context


def test_quality_pass_preserves_craft_instruction(monkeypatch) -> None:
    captured = {}

    async def fake_generate(provider, messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return "Revised prose"

    monkeypatch.setattr(craft, "generate", fake_generate)
    result = asyncio.run(
        craft.quality_pass(
            ProviderConfig(model="test-model"),
            draft="Draft prose",
            author_prompt="Keep this intense and intimate.",
            craft_context="Voice profile: clipped, tactile, dry humor.",
        )
    )

    assert result == "Revised prose"
    user_message = captured["messages"][1]["content"]
    assert "Draft prose" in user_message
    assert "clipped, tactile, dry humor" in user_message
    assert captured["kwargs"]["temperature"] == 0.35


def test_relevant_character_gets_dossier_context(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Character Voice Test")
    slug = project["slug"]
    storage.save_text(
        slug,
        "characters/sera.md",
        "# Sera\n\nSera speaks with deliberate precision. She dislikes sentimental euphemism.",
    )

    names = story_intelligence.relevant_character_names(
        slug,
        "Continue the scene with Sera after the council leaves.",
    )
    assert names == ["Sera"]

    context = story_intelligence.build_character_context(slug, names)
    assert "Dossier excerpt" in context
    assert "deliberate precision" in context
