"""Capitalized potential names are review hints, not automatic identities."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_name_candidates as names
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic candidate discovery")["id"]
    original = ("Ada met Nara Vale near the beacon. "
                "Ada told Nara Vale about Liora. "
                "The observer asked Liora to follow Ada. ")*12
    for book in (1, 2, 3):
        vault.import_volume(
            sid, f"fiction-{book}.md", original.encode(), book,
            title=f"Fiction {book}", kind="novel", edition_status="reference",
            rights_confirmed=True,
        )
    ada = canon.add_entity(sid, "Ada", "character")
    return sid, ada, original


def test_repeated_capitalized_leads_remain_unreviewed_and_cited(sample):
    sid, _ada, _ = sample
    result = names.propose(sid, min_books=2)
    assert result["scanned_sources"] == 3
    candidates = {c["label"]: c for c in result["candidates"]}
    assert "Nara Vale" in candidates
    assert "Liora" in candidates
    assert "Ada" not in candidates
    assert "The" not in candidates
    assert candidates["Nara Vale"]["books_with_mention"] == 3
    assert candidates["Nara Vale"]["literal_mention_count"] >= 60
    for candidate in (candidates["Nara Vale"], candidates["Liora"]):
        assert not candidate["character_identity_verified"]
        for hit in candidate["samples"]:
            record, text = vault.source_text(sid, hit["source_id"])
            assert record["sha256"] == hit["source_hash"]
            assert text[hit["start"]:hit["end"]] == candidate["label"]
            assert text[hit["excerpt_start"]:hit["excerpt_end"]] == hit["excerpt"]
    assert result["automatically_created_entities"] == 0
    only_liora = names.propose(sid, query="lio")
    assert [item["label"] for item in only_liora["candidates"]] == ["Liora"]
    assert only_liora["total_candidates"] == 1
    assert len(canon.list_entities(sid)) == 1


def test_creating_a_character_removes_it_from_future_unreviewed_leads(sample):
    sid, _, _ = sample
    assert any(c["label"] == "Nara Vale" for c in names.propose(sid)["candidates"])
    canon.add_entity(sid, "Nara Vale", "character")
    assert not any(c["label"] == "Nara Vale" for c in names.propose(sid)["candidates"])


def test_candidate_api_isolation_and_validation(sample):
    sid, _, _ = sample
    foreign = vault.create_series("Other book")["id"]
    with TestClient(app) as client:
        url = f"/api/series/{sid}/name-candidates"
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.json()["total_candidates"] >= 2
        assert client.get(url, params={"q": "Liora"}).json()["total_candidates"] == 1
        assert client.get(url+"?limit=0").status_code == 422
        assert client.get(f"/api/series/{foreign}/name-candidates").json()["total_candidates"] == 0
        assert client.get("/api/series/"+"f"*32+"/name-candidates").status_code == 404
