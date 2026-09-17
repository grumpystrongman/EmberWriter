from app.model_profiles import ollama_sampling_options, profile_catalog, profile_for_model


def test_catalog_explains_three_writing_jobs() -> None:
    catalog = profile_catalog()
    assert [item["key"] for item in catalog] == ["mature", "general", "planning"]
    assert "roleplay" in str(catalog[0]["why"]).lower() or "story" in str(catalog[0]["why"]).lower()
    assert "regular chapters" in str(catalog[1]["purpose"]).lower()
    assert "brainstorm" in str(catalog[2]["purpose"]).lower()


def test_rocinante_uses_story_sampler_not_old_global_penalty() -> None:
    profile = profile_for_model("HammerAI/rocinante-v1.1:12b-q4_K_M")
    assert profile is not None and profile.key == "mature"
    options = ollama_sampling_options(
        "HammerAI/rocinante-v1.1:12b-q4_K_M",
        temperature=0.9,
        top_p=0.95,
    )
    assert options["temperature"] == 0.72
    assert options["repeat_penalty"] == 1.03
    assert options["repeat_last_n"] == 128


def test_qwen3_uses_qwen_nonthinking_style_sampler() -> None:
    options = ollama_sampling_options("qwen3:8b", temperature=0.9, top_p=0.95)
    assert options["temperature"] == 0.70
    assert options["top_p"] == 0.80
    assert options["top_k"] == 20
    assert options["repeat_penalty"] == 1.0
    assert options["presence_penalty"] == 1.5


def test_low_temperature_verifier_is_not_made_creative() -> None:
    options = ollama_sampling_options(
        "HammerAI/rocinante-v1.1:12b-q4_K_M",
        temperature=0.0,
        top_p=0.8,
        json_mode=True,
    )
    assert options["temperature"] == 0.0
    assert options["top_p"] == 0.8
