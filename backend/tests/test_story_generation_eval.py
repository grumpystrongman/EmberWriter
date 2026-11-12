"""Deterministic, no-model-cost synthetic writing benchmark tests."""
import pytest
from app.story_generation_eval import SCENARIOS, inspect_text, run_benchmark

def test_repetition_named_entities_and_forbidden_truth_are_reported():
    scene=SCENARIOS[0]
    text="Ada met Bex near the gate.\n\n"+"The gate rang in the wind. "*110
    report=inspect_text(text,scene)
    assert report["missing_elements"]==[]
    assert not report["signals"]["no_high_5gram_repetition"]
    assert not report["passed"]
    forbidden=inspect_text("Ada realized the gate was dangerous.\n\nBex watched.",scene)
    assert forbidden["forbidden_reveals"]

def test_length_and_narrative_format_signals_independent():
    scene=SCENARIOS[1]
    report=inspect_text("Mara heard the bell.\n\nShe walked.",scene)
    assert not report["signals"]["length"]
    assert report["signals"]["named_elements"]
    assert report["signals"]["narrative_format"]
    assert report["elapsed_seconds"] is None

@pytest.mark.asyncio
async def test_remote_model_endpoint_is_prohibited_before_network():
    with pytest.raises(ValueError,match="loopback"):
        await run_benchmark("not-real",base_url="https://external-model.example")
    with pytest.raises(ValueError,match="Cloud or remote"):
        await run_benchmark("gemma4:31b-cloud")

def test_model_benchmark_job_is_explicit_and_local(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import storage, series_vault, story_benchmark_jobs as jobs
    from app.main import app
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series = series_vault.create_series("Benchmark Test Fiction")
    async def fake_benchmark(model, on_progress):
        on_progress(1, 3, {"name": "Character knowledge", "passed": True})
        return {"model": model, "passed": 1, "total": 3, "scenarios": []}
    monkeypatch.setattr(jobs, "run_benchmark", fake_benchmark)
    with TestClient(app) as client:
        base = f"/api/series/{series['id']}/model-evaluation"
        assert client.get(base).json()["status"] == "not_run"
        assert client.post(base, json={"model": "gemma4:31b-cloud"}).status_code == 400
        start = client.post(base, json={"model": "llama3.2:3b"})
        assert start.status_code == 202
        result = client.get(base).json()
        assert result["status"] == "completed"
        assert result["result"]["model"] == "llama3.2:3b"
        assert result["local_only"] is True
