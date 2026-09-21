import json

from app import model_provisioning


def test_best_creative_model_matches_runtime_ranking() -> None:
    models = [
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
        "HammerAI/rocinante-v1.1:12b-q4_K_M",
        "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M",
    ]
    assert model_provisioning._best_creative_model(models) == models[2]


def test_acceptance_cache_requires_matching_version_model_and_pass(tmp_path, monkeypatch) -> None:
    report = tmp_path / "writing-model-acceptance.json"
    monkeypatch.setattr(model_provisioning, "_ACCEPTANCE_PATH", report)
    model = "HammerAI/rocinante-v1.1:12b-q4_K_M"

    report.write_text(
        json.dumps(
            {
                "acceptance_version": model_provisioning._ACCEPTANCE_VERSION,
                "requested_model": model,
                "effective_models": [model],
                "passed": True,
            }
        ),
        encoding="utf-8",
    )
    assert model_provisioning._cached_acceptance_passed(model) is True

    payload = json.loads(report.read_text(encoding="utf-8"))
    payload["passed"] = False
    report.write_text(json.dumps(payload), encoding="utf-8")
    assert model_provisioning._cached_acceptance_passed(model) is False


def test_noncreative_model_is_not_selected() -> None:
    assert model_provisioning._best_creative_model(["qwen3:8b", "llama3.1:8b"]) is None


def test_provisioning_uses_separate_general_and_adult_capability_models() -> None:
    assert model_provisioning.BASELINE_CREATIVE_MODEL == model_provisioning.GENERAL_PROSE_MODEL
    assert model_provisioning.ADULT_EXPLICIT_CREATIVE_MODEL == model_provisioning.ADULT_EXPLICIT_MODEL
    assert model_provisioning._ADULT_BAKEOFF_MODELS == (model_provisioning.ADULT_EXPLICIT_MODEL,)


def test_persist_capability_preferences_maps_installed_models(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "local-models.json"
    monkeypatch.setattr(model_provisioning, "_LOCAL_MODELS_PATH", config_path)
    monkeypatch.setattr(model_provisioning, "_RUNTIME_DIR", tmp_path)

    installed = [
        model_provisioning.ADULT_EXPLICIT_MODEL,
        model_provisioning.GENERAL_PROSE_MODEL,
        model_provisioning.CHARACTER_MODEL,
        model_provisioning.FAST_MODEL,
    ]
    model_provisioning._persist_capability_preferences(installed)

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["adult_explicit_model"] == model_provisioning.ADULT_EXPLICIT_MODEL
    assert payload["general_prose_model"] == model_provisioning.GENERAL_PROSE_MODEL
    assert payload["character_model"] == model_provisioning.CHARACTER_MODEL
    assert payload["planning_model"] == model_provisioning.FAST_MODEL
    assert payload["preferred_model"] == model_provisioning.GENERAL_PROSE_MODEL
