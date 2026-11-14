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
    assert result["passed"] == result["total"] == 5
    assert len(calls) == 5
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
    assert result["passed"] == 4
    wrong = next(row for row in result["cases"] if row["id"] == "untrusted_note")
    assert not wrong["answer_correct"] and wrong["quote_correct"]


@pytest.mark.asyncio
async def test_timeout_marks_case_unverified(sid, monkeypatch):
    fake_client(monkeypatch, timeout_case="reader_cutoff")
    result = await quality.benchmark(sid, "fictional:3b")
    assert result["passed"] == 4
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
