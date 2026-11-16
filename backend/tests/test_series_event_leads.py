"""Literal timeline leads are exact source substrings, not automatic canon."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_event_leads as leads
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def story(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Temporal Synthetic")["id"]
    text = (
        "Before the storm, Ada locked the gate.\n"
        "After the storm, Ada unlocked the gate.\n"
        "Ada remembers the mountains from childhood.\n"
        "Meanwhile, Bex waits near the coast.\n"
        "Then the narrator tells us the moon is a green wagon.\n"
        "A sentence without time cues remains unclassified.\n"
    )
    detail = vault.import_volume(
        sid, "scene.md", text.encode(), 1, title="Book One",
        kind="novel", edition_status="approved", rights_confirmed=True,
    )
    source_id = detail["volumes"][0]["sources"][0]["id"]
    canon.add_entity(sid, "Ada", "character")
    canon.add_entity(sid, "Bex", "character")
    return sid, source_id, text


def test_literal_cues_are_exact_and_unapproved(story):
    sid, source_id, text = story
    results = leads.scan(sid)
    assert results["total"] >= 3
    assert results["canon_approved"] is False
    for item in results["leads"]:
        assert item["source_id"] == source_id
        assert text[item["quote_start"]:item["quote_end"]] == item["quote"]
        assert item["event_claimed"] is False
        assert item["chronology_inferred"] is False
        assert item["narrator_reliability_checked"] is False
        assert item["entities_mentioned"]
        assert item["literal_cues"]
    assert not any("moon is a green wagon" in item["quote"] for item in results["leads"])


def test_api_isolation_and_book_scope(story):
    sid, _, _ = story
    foreign = vault.create_series("Separate reference")["id"]
    with TestClient(app) as client:
        response = client.get(f"/api/series/{sid}/event-leads?book=1")
        assert response.status_code == 200, response.text
        assert response.json()["total"] >= 3
        assert client.get(f"/api/series/{sid}/event-leads?book=999").json()["total"] == 0
        assert client.get(f"/api/series/{foreign}/event-leads").json()["total"] == 0
        assert client.get("/api/series/" + "f" * 32 + "/event-leads").status_code == 404
        assert client.get(f"/api/series/{sid}/event-leads?limit=999").status_code == 422
