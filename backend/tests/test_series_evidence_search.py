"""Grounded local full-series search, spoiler cutoff, index rebuild, source offsets."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from test_series_bulk_import import _epub, _zip

from app import series_bulk_import, series_evidence_search, series_vault, storage
from app.main import app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    first = series_vault.create_series("Synthetic Chapter Evidence")
    other = series_vault.create_series("Neighbor Author's Book")
    archive = _zip([
        ("Tale 003 - Final Arrival.epub", _epub("Final Arrival")),
        ("Tale 001 - First Journey.epub", _epub("First Journey")),
        ("Tale 002 - Quiet Morning.epub", _epub("Quiet Morning")),
    ])
    series_bulk_import.import_epub_zip(first["id"], archive, rights_confirmed=True)
    series_bulk_import.import_epub_zip(
        other["id"], _zip([("Secret 001 - Hidden.epub", _epub("Hidden"))]),
        rights_confirmed=True,
    )
    return first["id"], other["id"]


def test_results_have_exact_source_offsets(setup):
    first_id, _ = setup
    result = series_evidence_search.search(first_id, "First Journey")
    assert result["books"] == 3 and result["sources"] == 3
    assert result["total_hits"] >= 1
    for hit in result["results"]:
        _, entire = series_vault.source_text(first_id, hit["source_id"])
        assert entire[hit["excerpt_start"]:hit["excerpt_end"]] == hit["excerpt"]
    assert result["disclaimer"].startswith("Literal source matches")


def test_temporal_filter_prevents_future_volume_leakage(setup):
    first_id, _ = setup
    future = series_evidence_search.search(first_id, "Final Arrival", max_book=2)
    assert not future["results"] and future["total_hits"] == 0
    later = series_evidence_search.search(first_id, "Final Arrival", min_book=3)
    assert later["total_hits"] >= 1
    assert all(row["book"] >= 3 for row in later["results"])


def test_separate_series_never_leak_and_query_syntax_is_safe(setup):
    first_id, other_id = setup
    assert series_evidence_search.search(first_id, "Hidden")["total_hits"] == 0
    assert series_evidence_search.search(other_id, "Hidden")["total_hits"] >= 1
    for question in ('" AND DROP TABLE chunks; --', "' OR 1=1 --"):
        # Search can return matches or none, but raw query syntax cannot run SQL.
        result = series_evidence_search.search(first_id, question)
        assert isinstance(result["results"], list)


def test_search_rebuilds_on_new_sources(setup):
    first_id, _ = setup
    previous = series_evidence_search.search(first_id, "New Journey")
    assert previous["total_hits"] == 0
    series_bulk_import.import_epub_zip(
        first_id,
        _zip([("Tale 004 - New Journey.epub", _epub("New Journey"))]),
        rights_confirmed=True,
    )
    result = series_evidence_search.search(first_id, "New Journey")
    assert result["total_hits"] >= 1
    assert result["books"] == 4


def test_search_http_endpoint(setup):
    first_id, _ = setup
    with TestClient(app) as client:
        response = client.get(
            f"/api/series/{first_id}/evidence-search",
            params={"query": "First Journey", "max_book": 1},
        )
        assert response.status_code == 200, response.text
        assert response.json()["total_hits"] >= 1
        invalid = client.get(
            f"/api/series/{first_id}/evidence-search",
            params={"query": "First Journey", "max_book": 0},
        )
        assert invalid.status_code == 422


def test_cited_search_result_opens_the_exact_original_position(setup):
    first_id, _ = setup
    result = series_evidence_search.search(first_id, "First Journey", limit=3)
    hit = result["results"][0]
    with TestClient(app) as client:
        original = client.get(
            f"/api/series/{first_id}/sources/{hit['source_id']}/excerpt",
            params={"query": "First Journey", "position": hit["excerpt_start"],
                    "limit": 1000},
        )
        assert original.status_code == 200, original.text
        passage = original.json()
        assert passage["found"] is True
        assert passage["excerpt_start"] <= hit["excerpt_start"] < passage["excerpt_end"]
        _, document = series_vault.source_text(first_id, hit["source_id"])
        assert document[passage["excerpt_start"]:passage["excerpt_end"]] == passage["excerpt"]
        invalid = client.get(
            f"/api/series/{first_id}/sources/{hit['source_id']}/excerpt",
            params={"position": len(document) + 100, "limit": 500},
        )
        assert invalid.status_code in (400, 422)
