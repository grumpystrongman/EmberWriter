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
