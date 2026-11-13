"""No manuscript leaves loopback during optional local model health checks."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import series_model_readiness as health
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def series_id(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    return vault.create_series("Private Synthetic Health Fixture")["id"]


def test_local_model_health_calls_tags_only_without_a_story(monkeypatch, series_id):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def get(self, url):
            calls.append(url)
            class Response:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"models": [{"name": "llama3.2:3b"},
                                       {"name": "remote:cloud"},
                                       {"name": "local:7b"}]}
            return Response()

    monkeypatch.setattr(health.httpx, "Client", Client)
    with TestClient(app) as client:
        response = client.get(f"/api/series/{series_id}/local-model-readiness")
    assert response.status_code == 200
    report = response.json()
    assert report["models"] == ["llama3.2:3b", "local:7b"]
    assert report["status"] == "available"
    assert report["source_text_sent"] is False
    assert report["generation_tested"] is False
    assert calls == ["http://127.0.0.1:11434/api/tags"]


def test_model_timeout_degrades_without_blocking_offline_research(monkeypatch, series_id):
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def get(self, url):
            raise httpx.ConnectTimeout("Synthetic local timeout")

    monkeypatch.setattr(health.httpx, "Client", Client)
    result = health.model_readiness(series_id)
    assert result["status"] == "timed_out"
    assert result["models"] == []
    assert result["source_text_sent"] is False
    assert "offline" in result["next_step"].lower()


def test_model_readiness_cannot_inspect_another_series(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    with TestClient(app) as client:
        response = client.get("/api/series/" + "f"*32 + "/local-model-readiness")
    assert response.status_code == 404
