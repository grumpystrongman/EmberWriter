"""Named dialogue cue scanning and author-only speaker/POV decisions."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_dialogue_leads as leads
from app import series_dialogue_reviews as reviews
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def story(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic Dialogues")["id"]
    text = ('Ada said "Close the golden gate before sundown." '
            '"The blue ship arrives before midnight," Bex replied. '
            '"I am speaking without any named cue here." The wind blew hard. '
            'Ada asked "Is the gateway still open tonight?" '
            '"Do not trust a dream," said Ada. '
            'Ada and Bex talked while "This has no immediate speech attribution."')
    volume = vault.import_volume(
        sid, "dialogue.md", text.encode(), 1, title="Book One",
        kind="novel", edition_status="reference", rights_confirmed=True,
    )
    ada = canon.add_entity(sid, "Ada", "character")
    bex = canon.add_entity(sid, "Bex", "character")
    source = volume["volumes"][0]["sources"][0]["id"]
    return sid, source, ada, bex, text


def test_explicit_named_dialogue_is_cited_but_not_approved(story):
    sid, source, ada, bex, content = story
    results = leads.scan(sid, book=1)
    assert results["total"] >= 3
    assert not results["auto_speaker_approved"] and not results["auto_pov_inferred"]
    for lead in results["leads"]:
        assert lead["source_id"] == source
        assert lead["speaker_verified"] is False
        assert lead["pov_inferred"] is False
        assert content[lead["quote_start"]:lead["quote_end"]] == lead["quote"]
        assert content[lead["context_start"]:lead["context_end"]] == lead["context"]
        assert any(h["entity_id"] in (ada["id"], bex["id"]) for h in lead["speaker_hints"])
    assert not any("I am speaking" in x["quote"] for x in results["leads"])


def test_stage_and_review_requires_real_character_and_exact_source(story):
    sid, source, ada, _bex, _text = story
    lead = leads.scan(sid, book=1)["leads"][0]
    staged = reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])
    assert staged["status"] == "proposed"
    assert not staged["author_confirmed_speaker"]
    assert len(reviews.list_reviews(sid)) == 1
    assert reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])["id"] == staged["id"]
    with pytest.raises(ValueError, match="Choose an actual speaker"):
        reviews.decide(sid, staged["id"], decision="approved")
    with pytest.raises(ValueError, match="must be a character"):
        reviews.decide(sid, staged["id"], decision="approved", speaker_id="bogus")
    with pytest.raises(ValueError, match="not a verified"):
        reviews.stage(sid, source, lead["quote_start"]+1, lead["quote_end"])
    accepted = reviews.decide(sid, staged["id"], decision="approved",
                              speaker_id=ada["id"], pov_class="not_determined",
                              note="Reader manually checked attribution.")
    assert accepted["author_confirmed_speaker"]
    assert accepted["pov_class"] == "not_determined"
    assert canon.list_facts(sid) == []


def test_http_isolation_book_filter_and_rejection(story):
    sid, source, _ada, _bex, _content = story
    foreign = vault.create_series("Different Author")["id"]
    with TestClient(app) as client:
        r = client.get(f"/api/series/{sid}/dialogue-leads?book=1")
        assert r.status_code == 200, r.text
        lead = r.json()["leads"][0]
        assert client.get(f"/api/series/{sid}/dialogue-leads?book=2").json()["total"] == 0
        assert client.get(f"/api/series/{sid}/dialogue-leads?book=1&limit=101").status_code == 422
        assert client.get(f"/api/series/{foreign}/dialogue-leads?book=1").json()["total"] == 0
        created = client.post(f"/api/series/{sid}/dialogue-reviews", json={
            "source_id": source,
            "quote_start": lead["quote_start"], "quote_end": lead["quote_end"],
        })
        assert created.status_code == 201, created.text
        rid = created.json()["id"]
        assert client.get(f"/api/series/{foreign}/dialogue-reviews").json() == []
        assert client.post(f"/api/series/{foreign}/dialogue-reviews/{rid}/decision",
                           json={"decision": "rejected"}).status_code == 404
        rejected = client.post(f"/api/series/{sid}/dialogue-reviews/{rid}/decision",
                               json={"decision": "rejected", "note": "Not a spoken line"})
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert not rejected.json()["author_confirmed_speaker"]
        assert len(client.get(f"/api/series/{sid}/dialogue-reviews?book=1").json()) == 1
