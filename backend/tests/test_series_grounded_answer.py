"""Synthetic-only grounded answer tests."""
import json

import pytest
from fastapi.testclient import TestClient

from app import series_grounded_answer as service
from app.main import app


@pytest.fixture
def setup(monkeypatch):
    texts = ["Mira guards the old stone bridge.", "Mira repairs the damaged stone bridge.",
             "Mira destroys the old stone bridge."]
    rows = [{"book": i + 1, "source_id": str(i), "excerpt": text,
             "excerpt_start": 10, "excerpt_end": 10 + len(text)}
            for i, text in enumerate(texts)]
    monkeypatch.setattr(service.search, "search", lambda *a, **k: {"results": rows})
    monkeypatch.setattr(service.readiness, "model_readiness", lambda *_: {
        "status": "available", "models": ["local:latest"]})
    return rows


def fake_model(monkeypatch, draft):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"response": json.dumps(draft)}
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
            assert kwargs["follow_redirects"] is False
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def post(self, url, json):
            assert url == "http://127.0.0.1:11434/api/generate"
            assert "destroys" not in json["prompt"]
            return Response()
    monkeypatch.setattr(service.httpx, "Client", Client)


def test_multiple_citations_and_cutoff(setup, monkeypatch):
    fake_model(monkeypatch, {"answer": "Mira changes from guarding to repairing the bridge.",
        "citations": [{"passage": 0, "quote": setup[0]["excerpt"]},
                      {"passage": 1, "quote": setup[1]["excerpt"]}]})
    result = service.answer("series", "How did Mira change across books?", "Mira", 2, "local:latest")
    assert result["status"] == "review"
    assert result["semantic_entailment"] == "unverified"
    assert result["auto_approval_allowed"] is False
    assert [c["start"] for c in result["citations"]] == [10, 10]
    assert len(result["passages"]) == 2


@pytest.mark.parametrize("answer,citations,question", [
    ("Mira", [{"passage": 0, "quote": "Mira guards the old stone bridge."}], "What does Mira do?"),
    ("She repairs it.", [{"passage": 1, "quote": "Mira repairs the damaged stone bridge."}], "How did Mira change across books?"),
    ("She guards it.", [{"passage": 0, "quote": "Mira guards"}], "What does Mira do?"),
    ("She guards it.", [{"passage": 0, "quote": "Mira flies across the old stone bridge."}], "What does Mira do?"),
    ("She guards it.", [], "What does Mira do?"),
])
def test_rejects_bad_drafts(setup, monkeypatch, answer, citations, question):
    fake_model(monkeypatch, {"answer": answer, "citations": citations})
    result = service.answer("series", question, "Mira", 2, "local:latest")
    assert result["status"] == "abstain"
    assert result["answer"] is None and result["citations"] == []


def test_route_and_model_selection(setup):
    with TestClient(app) as client:
        payload = {"question": "What does Mira do?", "query": "Mira", "as_of_book": 1}
        response = client.post("/api/series/synthetic/grounded-answer", json=payload)
        assert response.status_code == 200
        assert len(response.json()["passages"]) == 1
        payload["model"] = "remote:cloud"
        assert client.post("/api/series/synthetic/grounded-answer", json=payload).status_code == 400
