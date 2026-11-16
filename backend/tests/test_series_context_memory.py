"""Cumulative contextual research stays private, source-linked, and review-gated."""
import json

import pytest
from fastapi.testclient import TestClient

from app import series_context_memory as memory
from app.main import app

SID = "a" * 32
CARD = "b" * 64


@pytest.fixture
def vault_context(tmp_path, monkeypatch):
    monkeypatch.setattr(memory.vault, "_root", lambda: tmp_path)
    monkeypatch.setattr(memory.vault, "series_detail", lambda sid: {"id": sid})
    monkeypatch.setattr(memory.vault, "source_text",
                        lambda sid, source_id: ({"id": source_id}, "Mira guards the old stone bridge."))
    card = {
        "schema": "local_context_proposal.v1", "id": CARD, "as_of_book": 2,
        "question": "How does Mira become the keeper?",
        "interpretation": "Mira becomes the keeper after her apprenticeship.",
        "facet": "development", "status": "pending_author_review",
        "citations": [{"book": 2, "source_id": "source1",
                       "start": 0, "end": 19}],
    }
    (tmp_path / f"context-proposals-{SID}.jsonl").write_text(
        json.dumps(card) + "\n", encoding="utf-8")
    return tmp_path


def test_list_requires_source_and_book_bounds(vault_context):
    result = memory.list_candidates(SID, max_book=2)
    assert len(result["items"]) == 1
    assert result["items"][0]["review_state"] == "pending_author_review"
    assert result["auto_canon_approved"] is False
    assert memory.list_candidates(SID, max_book=1)["items"] == []


def test_review_rejects_invalid_status_and_identifier(vault_context):
    with pytest.raises(ValueError):
        memory.review(SID, CARD, "approved_canon")
    with pytest.raises(ValueError):
        memory.review(SID, "not-a-sha", "confirmed_for_research")


def test_confirm_is_research_only_and_can_be_used_later(vault_context):
    reply = memory.review(SID, CARD, "confirmed_for_research")
    assert reply["review_state"] == "confirmed_for_research"
    assert reply["auto_canon_approved"] is False
    assert reply["independent_expert_review"] is False
    info = memory.approved_research_context(
        SID, "Mira become keeper", as_of_book=2)
    assert len(info) == 1
    assert info[0]["status"] == "author_confirmed_for_research_not_canon"
    assert memory.approved_research_context(SID, "Mira keeper", as_of_book=1) == []


def test_rejection_never_enters_context(vault_context):
    memory.review(SID, CARD, "rejected")
    assert memory.approved_research_context(
        SID, "Mira keeper", as_of_book=2) == []


def test_source_offsets_checked_before_confirmation(vault_context, monkeypatch):
    monkeypatch.setattr(memory.vault, "source_text",
                        lambda *_: ({}, "short"))
    with pytest.raises(ValueError, match="Source"):
        memory.review(SID, CARD, "confirmed_for_research")


def test_api_lists_and_reviews_only_author_requested_context(vault_context):
    with TestClient(app) as client:
        response = client.get(
            f"/api/series/{SID}/context-proposals?max_book=2")
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == CARD
        bad = client.post(
            f"/api/series/{SID}/context-proposals/{CARD}/review",
            json={"decision": "approved_canon"})
        assert bad.status_code == 422
        good = client.post(
            f"/api/series/{SID}/context-proposals/{CARD}/review",
            json={"decision": "confirmed_for_research"})
        assert good.status_code == 200
        assert good.json()["auto_canon_approved"] is False


def test_missing_context_file_does_not_invent_knowledge(tmp_path, monkeypatch):
    monkeypatch.setattr(memory.vault, "_root", lambda: tmp_path)
    monkeypatch.setattr(memory.vault, "series_detail", lambda sid: {"id": sid})
    assert memory.list_candidates(SID)["items"] == []
    assert memory.approved_research_context(SID, "any", as_of_book=9999) == []
