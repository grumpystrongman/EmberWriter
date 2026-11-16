"""Synthetic, privacy-preserving contextual interpretation tests."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import series_context_answer as context
from app.main import app


@pytest.fixture
def setup(monkeypatch):
    excerpts = {
        "s1": (1, "Mira trains at the old stone bridge each morning."),
        "s2": (2, "Mira becomes the bridge keeper after her apprenticeship."),
    }
    rows = [
        {"book": book, "source_id": sid, "excerpt": text, "excerpt_start": 10,
         "excerpt_end": 10 + len(text), "volume": f"Volume {book}"}
        for sid, (book, text) in excerpts.items()
    ]
    memory = []
    monkeypatch.setattr(context, "_collect", lambda *a, **k: rows)
    monkeypatch.setattr(context.memory, "approved_research_context",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(context.readiness, "model_readiness",
                        lambda *_: {"status": "available", "models": ["local:latest"]})
    monkeypatch.setattr(context.vault, "source_text",
                        lambda sid, source_id: ({"id": source_id},
                            "0123456789" + excerpts[source_id][1] + " tail"))
    monkeypatch.setattr(context, "_append_provisional", lambda _id, card: memory.append(card))
    return rows, memory


def fake_response(monkeypatch, *, answer, references, verify="supported"):
    outputs = iter([
        {"answer": answer, "passage_ids": references, "uncertainty": ""},
        {"support": verify, "reason": "Source evidence reviewed locally"},
    ])
    monkeypatch.setattr(context, "_local_call",
                        lambda *args, **kwargs: next(outputs))


def test_contextual_answer_can_synthesize_and_keep_author_review(setup, monkeypatch):
    rows, memory = setup
    fake_response(monkeypatch,
                  answer="Mira trains and later becomes the bridge keeper.",
                  references=[0, 1])
    result = context.answer("series", "How did Mira change between books 1 and 2?",
                            "Mira", 2, "local:latest")
    assert result["status"] == "provisional"
    assert result["answer"]
    assert len(result["citations"]) == 2
    assert [c["book"] for c in result["citations"]] == [1, 2]
    assert result["auto_approval_allowed"] is False
    assert result["semantic_entailment"] == "unverified"
    assert memory[0]["status"] == "pending_author_review"
    assert not any("quote" in source for source in memory[0]["citations"])


def test_local_verifier_rejects_unrelated_murder_claim(setup, monkeypatch):
    _, memory = setup
    fake_response(monkeypatch, answer="Mira murdered the king last winter.",
                  references=[0], verify="unsupported")
    result = context.answer("series", "What did Mira do?", "Mira", 2, "local:latest")
    assert result["status"] == "abstain"
    assert result["reasons"] == ["local_verifier_unsupported"]
    assert not memory


def test_comparison_needs_before_and_after_citations(setup, monkeypatch):
    _, memory = setup
    fake_response(monkeypatch, answer="Mira later tends a bridge.", references=[0])
    result = context.answer("series", "How did Mira change between books 1 and 2?",
                            "Mira", 2, "local:latest")
    assert result["status"] == "abstain"
    assert result["reasons"] == ["missing_before_after_citations"]
    assert not memory


def test_invalid_passage_id_rejected(setup, monkeypatch):
    _, memory = setup
    fake_response(monkeypatch, answer="Mira trains at the bridge.",
                  references=[9])
    result = context.answer("series", "What does Mira do?", "Mira", 2, "local:latest")
    assert result["status"] == "abstain"
    assert result["reasons"] == ["model_invalid_evidence_references"]
    assert not memory


def test_future_book_question_never_retrieves(setup, monkeypatch):
    monkeypatch.setattr(context, "_collect", lambda *a, **k:
                        pytest.fail("future book retrieval"))
    result = context.answer("series", "Compare Mira in books 1 and 5",
                            "Mira", 2, "local:latest")
    assert result["reasons"] == ["future_book_cutoff"]


def test_snapshot_mismatch_prevents_author_proposal(setup, monkeypatch):
    _, memory = setup
    monkeypatch.setattr(context.vault, "source_text",
                        lambda *args: ({}, "a stale or unrelated text"))
    fake_response(monkeypatch, answer="Mira trains at the bridge.",
                  references=[0])
    result = context.answer("series", "What does Mira do?", "Mira", 2, "local:latest")
    assert result["status"] == "abstain"
    assert result["reasons"] == ["source_snapshot_mismatch"]
    assert not memory


def test_explanation_falls_back_to_specific_model_errors(setup, monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(context, "_local_call", fail)
    result = context.answer("series", "What does Mira do?", "Mira", 2, "local:latest")
    assert result["reasons"] == ["model_timeout"]


def test_model_wont_be_replaced_with_cloud_tag(setup):
    with pytest.raises(ValueError, match="local Ollama"):
        context.answer("series", "What does Mira do?", "Mira", 2, "model:cloud")


def test_grounded_route_uses_contextual_path_for_model(monkeypatch, setup):
    fake_response(monkeypatch, answer="Mira trains at the bridge.", references=[0])
    with TestClient(app) as client:
        response = client.post("/api/series/synthetic/grounded-answer",
            json={"question": "What does Mira do?", "query": "Mira",
                  "as_of_book": 2, "model": "local:latest"})
        assert response.status_code == 200
        assert response.json()["status"] == "provisional"


def test_query_variants_are_bounded_and_distinct():
    variants = context._queries("What happened to Mira after the training?",
                                "Mira stone bridge")
    assert variants[0] == "Mira stone bridge"
    assert len(variants) <= 4
    assert len(variants) == len(set(variants))
