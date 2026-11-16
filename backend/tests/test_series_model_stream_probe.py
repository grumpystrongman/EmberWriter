"""Synthetic bounded streaming probe: exact answer, incomplete/error, cancellation."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import series_model_readiness as readiness
from app import series_model_stream_probe as stream_probe
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(readiness, "model_readiness",
                        lambda _: {"status": "available", "models": ["synthetic:3b"]})
    return vault.create_series("Imaginary Streaming Test")["id"]


def client_factory(monkeypatch, lines):
    captures = []

    class Response:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in lines:
                if isinstance(line, Exception):
                    raise line
                yield json.dumps(line)

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        def stream(self, method, url, **kwargs):
            captures.append((method, url, kwargs))
            class Stream:
                async def __aenter__(self):
                    return Response()
                async def __aexit__(self, *_):
                    pass
            return Stream()

    monkeypatch.setattr(stream_probe.httpx, "AsyncClient", Client)
    return captures


@pytest.mark.asyncio
async def test_success_measures_first_token_and_ollama_metrics(sid, monkeypatch):
    captures = client_factory(monkeypatch, [
        {"response": '{"answer":"Rowan",', "done": False},
        {"response": '"quote":"Mira protects Rowan."}', "done": False},
        {"response": "", "done": True, "load_duration": 3_000_000,
         "prompt_eval_duration": 7_000_000, "eval_duration": 12_000_000,
         "prompt_eval_count": 25, "eval_count": 14},
    ])
    result = await stream_probe.probe(sid, "synthetic:3b")
    assert result["status"] == "passed"
    assert result["first_token_ms"] is not None
    assert result["load_ms"] == 3.0
    assert result["prompt_eval_ms"] == 7.0
    assert result["generation_ms"] == 12.0
    assert result["stream_completed"]
    assert result["generated_tokens"] == 14
    assert result["tokens_per_second"] == 1166.7
    assert result["source_text_sent"] is False
    assert captures[0][0:2] == ("POST", stream_probe.LOOPBACK_URL)
    assert captures[0][2]["json"]["stream"] is True
    assert "Mira protects Rowan" in captures[0][2]["json"]["prompt"]


@pytest.mark.asyncio
async def test_wrong_answer_does_not_pass(sid, monkeypatch):
    client_factory(monkeypatch, [
        {"response": '{"answer":"Mira","quote":"invented"}', "done": True},
    ])
    result = await stream_probe.probe(sid, "synthetic:3b")
    assert result["status"] == "incorrect"
    assert not result["exact_answer_verified"]


@pytest.mark.asyncio
async def test_missing_done_marker_stays_incomplete(sid, monkeypatch):
    client_factory(monkeypatch, [{"response": '{"answer":"Rowan"}', "done": False}])
    result = await stream_probe.probe(sid, "synthetic:3b")
    assert result["status"] == "incomplete"
    assert not result["stream_completed"]
    assert result["tokens_per_second"] is None


@pytest.mark.asyncio
async def test_model_timeout_is_not_mislabeled(sid, monkeypatch):
    client_factory(monkeypatch, [httpx.ReadTimeout("synthetic timeout")])
    result = await stream_probe.probe(sid, "synthetic:3b")
    assert result["status"] == "timed_out"
    assert not result["exact_answer_verified"]


@pytest.mark.asyncio
async def test_excessive_stream_truncates(sid, monkeypatch):
    client_factory(monkeypatch, [
        {"response": "x" * (stream_probe.MAX_RESPONSE_CHARS + 1), "done": True},
    ])
    result = await stream_probe.probe(sid, "synthetic:3b")
    assert result["status"] == "response_limit"
    assert not result["exact_answer_verified"]


@pytest.mark.asyncio
async def test_disconnected_client_cancels_running_model(sid, monkeypatch):
    cancellation = asyncio.Event()
    async def hangs(_):
        try:
            await asyncio.sleep(30)
        finally:
            cancellation.set()
    monkeypatch.setattr(stream_probe, "_generate", hangs)
    async def disconnected():
        return True
    with pytest.raises(asyncio.CancelledError):
        await stream_probe.probe(sid, "synthetic:3b", is_disconnected=disconnected)
    assert cancellation.is_set()


def test_api_requires_existing_series_and_valid_model(sid):
    with TestClient(app) as client:
        response = client.post(
            "/api/series/" + "f" * 32 + "/local-model-stream-probe",
            json={"model": "synthetic:3b"},
        )
        assert response.status_code == 404
        response = client.post(
            f"/api/series/{sid}/local-model-stream-probe",
            json={"model": "not-installed"},
        )
        assert response.status_code == 400
