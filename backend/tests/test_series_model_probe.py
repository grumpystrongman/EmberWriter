"""Local model proof remains synthetic, opt-in, timeout bounded, private."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import series_model_probe as probe
from app import series_model_readiness as readiness
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def series_id(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    return vault.create_series("Synthetic Readiness")["id"]


def _ready(series_id, monkeypatch):
    monkeypatch.setattr(
        readiness, "model_readiness",
        lambda sid: {"status": "available", "models": ["local:3b"]},
    )


@pytest.mark.asyncio
async def test_model_probe_proves_synthetic_exact_answer_without_book_text(series_id, monkeypatch):
    _ready(series_id, monkeypatch)
    captured = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, **kwargs):
            captured.append((url, kwargs))
            class Response:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"response": json.dumps({
                        "answer": "Rowan", "quote": "Mira protects Rowan."
                    })}
            return Response()

    monkeypatch.setattr(probe.httpx, "AsyncClient", Client)
    result = await probe.probe(series_id, "local:3b")
    assert result["status"] == "passed"
    assert result["exact_answer_verified"]
    assert result["elapsed_ms"] >= 0
    assert result["source_text_sent"] is False
    assert result["synthetic_question_only"]
    assert captured[0][0] == "http://127.0.0.1:11434/api/generate"
    assert captured[0][1]["json"]["stream"] is False
    assert "Mira protects Rowan." in captured[0][1]["json"]["prompt"]


@pytest.mark.asyncio
async def test_model_probe_bad_answer_does_not_get_a_pass(series_id, monkeypatch):
    _ready(series_id, monkeypatch)
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, **kwargs):
            class Response:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"response": '{"answer":"Mira","quote":"invented"}'}
            return Response()

    monkeypatch.setattr(probe.httpx, "AsyncClient", Client)
    result = await probe.probe(series_id, "local:3b")
    assert result["status"] == "incorrect"
    assert result["generation_tested"] is True
    assert result["exact_answer_verified"] is False


@pytest.mark.asyncio
async def test_probe_timeout_is_reported_as_failure_not_success(series_id, monkeypatch):
    _ready(series_id, monkeypatch)
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, **kwargs):
            raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(probe.httpx, "AsyncClient", Client)
    result = await probe.probe(series_id, "local:3b")
    assert result["status"] == "timed_out"
    assert not result["exact_answer_verified"]


def test_probe_disallows_uninstalled_models_and_cross_series(series_id, monkeypatch):
    _ready(series_id, monkeypatch)
    with pytest.raises(ValueError, match="currently installed"):
        asyncio.run(probe.probe(series_id, "not-installed"))
    with TestClient(app) as client:
        assert client.post(
            "/api/series/" + "f"*32 + "/local-model-probe",
            json={"model": "local:3b"},
        ).status_code == 404
