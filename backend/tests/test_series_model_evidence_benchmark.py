"""Exact, predeclared synthetic evidence grading with no private book text."""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import series_model_evidence_benchmark as quality
from app import series_model_readiness as readiness
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(readiness, "model_readiness",
                        lambda _: {"status": "available", "models": ["fictional:3b"]})
    return vault.create_series("Independent Gold Synthetic Cases")["id"]


def fake_client(monkeypatch, *, wrong_case=None, timeout_case=None):
    captured = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        async def post(self, url, *, json):
            assert url == quality.LOOPBACK
            captured.append(json)
            case = next(case for case in quality.CASES if case["source"] in json["prompt"])
            if case["id"] == timeout_case:
                raise httpx.ReadTimeout("synthetic timeout")
            expected = {
                "answer": "indigo" if case["id"] == wrong_case else case["answer"],
                "quote": case["quote"],
            }
            class Response:
                def raise_for_status(self):
                    pass
                def json(self):
                    return {"response": __import__("json").dumps(expected)}
            return Response()

    monkeypatch.setattr(quality.httpx, "AsyncClient", Client)
    return captured


@pytest.mark.asyncio
async def test_all_synthetic_questions_exactly_scored(sid, monkeypatch):
    calls = fake_client(monkeypatch)
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["status"] == "passed"
    assert result["passed"] == result["total"] == 10
    assert len(calls) == 10
    assert all(row["status"] == "passed" and row["quote_correct"] for row in result["cases"])
    assert all(call["model"] == "fictional:3b" and call["stream"] is False and call["think"] is False for call in calls)
    assert all("REFERENCE BEGINS" in call["prompt"] for call in calls)
    assert not result["auto_approval_allowed"]
    assert result["source_text_sent"] is False


@pytest.mark.asyncio
async def test_one_wrong_answer_is_partial_not_passed(sid, monkeypatch):
    fake_client(monkeypatch, wrong_case="untrusted_note")
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["status"] == "partial"
    assert result["passed"] == 9
    wrong = next(row for row in result["cases"] if row["id"] == "untrusted_note")
    assert not wrong["answer_correct"] and wrong["quote_correct"]


@pytest.mark.asyncio
async def test_timeout_marks_case_unverified(sid, monkeypatch):
    fake_client(monkeypatch, timeout_case="reader_cutoff")
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["passed"] == 9
    wrong = next(row for row in result["cases"] if row["id"] == "reader_cutoff")
    assert wrong["status"] == "timed_out"
    assert not wrong["quote_correct"]


@pytest.mark.asyncio
async def test_disconnection_cancels_active_benchmark(sid, monkeypatch):
    cancelled = asyncio.Event()
    async def never_finishes(model):
        try:
            await asyncio.sleep(40)
        finally:
            cancelled.set()
    monkeypatch.setattr(quality, "_evaluate", never_finishes)
    async def disconnected():
        return True
    with pytest.raises(asyncio.CancelledError):
        await quality.benchmark(sid, "fictional:3b", is_disconnected=disconnected)
    assert cancelled.is_set()


def test_api_isolation_and_installed_model_enforced(sid):
    with TestClient(app) as client:
        assert client.post(
            "/api/series/" + "f" * 32 + "/local-model-evidence-benchmark",
            json={"model": "fictional:3b"},
        ).status_code == 404
        assert client.post(
            f"/api/series/{sid}/local-model-evidence-benchmark",
            json={"model": "uninstalled:8b"},
        ).status_code == 400

@pytest.mark.asyncio
async def test_wall_timeout_preserves_completed_cases(sid, monkeypatch):
    calls = fake_client(monkeypatch)
    original = quality.httpx.AsyncClient.post
    async def slow(self, url, *, json):
        if len(calls) == 1:
            await asyncio.sleep(1)
        return await original(self, url, json=json)
    monkeypatch.setattr(quality.httpx.AsyncClient, "post", slow)
    monkeypatch.setattr(quality, "MAX_WALL_SECONDS", 0.05)
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["status"] == "timed_out"
    assert result["passed"] == 1
    assert result["cases"][0]["status"] == "passed"
    assert all(row["status"] == "not_run" for row in result["cases"][1:])
    assert len(result["case_set_sha256"]) == 64


@pytest.mark.asyncio
async def test_case_wall_timeout_continues_to_next_case(sid, monkeypatch):
    calls = fake_client(monkeypatch)
    original = quality.httpx.AsyncClient.post
    async def slow(self, url, *, json):
        if not calls:
            calls.append(json)
            await asyncio.sleep(1)
        return await original(self, url, json=json)
    monkeypatch.setattr(quality.httpx.AsyncClient, "post", slow)
    monkeypatch.setattr(quality, "CASE_TIMEOUT_SECONDS", 0.02)
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["cases"][0]["status"] == "timed_out"
    assert result["passed"] == 9

@pytest.mark.asyncio
async def test_abstention_requires_empty_quote(sid, monkeypatch):
    fake_client(monkeypatch)
    original = quality.httpx.AsyncClient.post
    async def fabricated_quote(self, url, *, json):
        response = await original(self, url, json=json)
        if quality.CASES[-1]["source"] in json["prompt"]:
            response.json = lambda: {"response": '{"answer":"unknown","quote":"invented"}'}
        return response
    monkeypatch.setattr(quality.httpx.AsyncClient, "post", fabricated_quote)
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["cases"][-1]["status"] == "incorrect"
    assert result["cases"][-1]["answer_correct"]
    assert not result["cases"][-1]["quote_correct"]
