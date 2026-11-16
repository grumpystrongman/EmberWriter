"""Event review requires explicit interpretation and exact source evidence."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_event_leads as leads
from app import series_event_reviews as reviews
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def story(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic Author Timeline")["id"]
    passage = ("Before the storm, Ada locked the garden gate. "
               "After the storm, Ada remembers the gate was unlocked.")
    detail = vault.import_volume(sid, "fiction.md", passage.encode(), 1,
                                 title="Fiction", kind="novel", edition_status="reference",
                                 rights_confirmed=True)
    source = detail["volumes"][0]["sources"][0]["id"]
    canon.add_entity(sid, "Ada", "character")
    lead = leads.scan(sid, book=1)["leads"][0]
    return sid, source, passage, lead


def test_event_staging_does_not_make_claims_true(story):
    sid, source, passage, lead = story
    result = reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])
    assert result["status"] == "proposed"
    assert result["source_verified"]
    assert not result["automatically_approved"]
    assert not result["is_author_approved"]
    assert result["quote"] in passage
    assert reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])["id"] == result["id"]
    assert not canon.list_facts(sid)
    assert reviews.list_events(sid, status="approved")["total_visible"] == 0
    with pytest.raises(ValueError):
        reviews.stage(sid, source, lead["quote_start"]+1, lead["quote_end"])


def test_event_approval_requires_human_narrative_context(story):
    sid, source, _, lead = story
    staged = reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])
    with pytest.raises(ValueError, match="explicit title"):
        reviews.review(sid, staged["id"], decision="approved")
    with pytest.raises(ValueError, match="valid event"):
        reviews.review(sid, staged["id"], decision="approved",
                       title="Gate closed", event_kind="guessed")
    accepted = reviews.review(sid, staged["id"], decision="approved",
                              title="Ada closed the gate", event_kind="observed_event",
                              timeline_class="book_sequence", note="Author verified context")
    assert accepted["is_author_approved"] is True
    assert accepted["timeline_class"] == "book_sequence"
    assert len(reviews.list_events(sid, status="approved")["events"]) == 1
    # Author accepted an independently reviewed event, not a generic world fact.
    assert canon.list_facts(sid) == []


def test_event_reject_and_series_isolation_http(story):
    sid, source, _, lead = story
    foreign = vault.create_series("Other Private Novel")["id"]
    with TestClient(app) as client:
        uri = f"/api/series/{sid}/event-reviews"
        created = client.post(uri, json={
            "source_id": source, "quote_start": lead["quote_start"],
            "quote_end": lead["quote_end"],
        })
        assert created.status_code == 201, created.text
        record = created.json()
        assert record["status"] == "proposed"
        assert client.get(uri, params={"status": "approved"}).json()["total_visible"] == 0
        denied = client.post(
            f"/api/series/{foreign}/event-reviews/{record['id']}/decision",
            json={"decision": "rejected"},
        )
        assert denied.status_code == 404
        decision = client.post(uri + f"/{record['id']}/decision",
                               json={"decision": "rejected", "note": "Metaphorical"})
        assert decision.status_code == 200, decision.text
        assert decision.json()["status"] == "rejected"
        assert client.get(uri, params={"status": "approved"}).json()["total_visible"] == 0
        assert client.get(uri, params={"status": "rejected"}).json()["total_visible"] == 1
