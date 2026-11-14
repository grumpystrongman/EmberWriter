"""Literal cross-book character evidence, immutable coordinates and series isolation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_character_presence as presence
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Fictional Character Atlas")["id"]
    one = "Ada waved at Bex. Ada remembered the lighthouse. Adam crossed the bridge.\n"
    two = "Bex wrote Ada a letter. Ada walked into the harbor.\n"
    for book, content in [(1, one), (2, two)]:
        vault.import_volume(sid, f"fiction-{book}.md", content.encode(), book,
                            title=f"Book {book}", kind="novel",
                            edition_status="reference", rights_confirmed=True)
    ada = canon.add_entity(sid, "Ada", "character", aliases=["The Navigator"])
    bex = canon.add_entity(sid, "Bex", "character")
    return sid, ada, bex, one, two


def test_literal_mentions_and_exact_offsets_across_books(sample):
    sid, ada, _bex, _one, _two = sample
    result = presence.atlas(sid, entity_id=ada["id"])
    assert result["entity_name"] == "Ada"
    assert result["books_examined"] == result["books_with_mentions"] == 2
    assert result["total_literal_mentions"] == 4
    assert [b["mention_count"] for b in result["books"]] == [2, 2]
    for item in result["books"]:
        source, content = vault.source_text(sid, item["samples"][0]["source_id"])
        for match in item["samples"]:
            assert content[match["mention_start"]:match["mention_end"]] == match["mention"]
            assert content[match["excerpt_start"]:match["excerpt_end"]] == match["excerpt"]
            assert source["sha256"] == match["source_hash"]
            assert match["verified_original_epub"] is False
    assert result["nearby_character_names"][0]["name"] == "Bex"
    assert result["author_approved_facts_created"] == 0
    assert canon.list_facts(sid) == []


def test_aliases_and_similar_substrings_do_not_create_false_counts(sample):
    sid, ada, _, _, _ = sample
    canon.edit_entity(sid, ada["id"], aliases=["The Navigator"], description="")
    result = presence.atlas(sid, entity_id=ada["id"], min_book=1, max_book=1)
    assert result["total_literal_mentions"] == 2
    assert result["books_examined"] == 1
    assert result["books_with_mentions"] == 1


def test_atlas_api_fails_closed_for_foreign_series_and_types(sample):
    sid, ada, bex, _, _ = sample
    foreign = vault.create_series("Separate Story")["id"]
    place = canon.add_entity(sid, "Harbor", "place")
    with TestClient(app) as client:
        url = f"/api/series/{sid}/character-presence"
        response = client.get(url, params={"entity_id": ada["id"], "min_book": 2})
        assert response.status_code == 200, response.text
        assert response.json()["total_literal_mentions"] == 2
        assert client.get(url, params={"entity_id": place["id"]}).status_code == 400
        assert client.get(url, params={"entity_id": bex["id"], "max_book": 0}).status_code == 422
        assert client.get(f"/api/series/{foreign}/character-presence",
                          params={"entity_id": ada["id"]}).status_code == 404
        assert client.get(url, params={"entity_id": "unknown"}).status_code == 404
