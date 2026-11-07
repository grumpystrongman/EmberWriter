"""End-to-end synthetic Series Vault / Canon Graph / time-aware evidence contracts."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def series_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series = vault.create_series("The Lantern Cycle", "A private synthetic fantasy series")
    first = (
        "Lyra placed the Moon Key in the glass vault. "
        "Lyra believes the key is harmless. "
        "Readers learn the key opens the sealed gate."
    )
    second = (
        "Lyra moved the Moon Key to the sunlit tower. "
        "Lyra discovers the key burns living wood. "
        "Readers learn the glass vault was empty."
    )
    vault.import_volume(series["id"], "one.md", first.encode("utf-8"), 1,
                        title="The First Lantern", kind="novel",
                        edition_status="published", rights_confirmed=True)
    vault.import_volume(series["id"], "two.txt", second.encode("utf-8"), 2,
                        title="The Second Lantern", kind="novel",
                        edition_status="published", rights_confirmed=True)
    detail = vault.series_detail(series["id"])
    return series["id"], detail["volumes"], first, second


def _add_fact(series_id, sources, character, subject, content, phrase,
              book, scope="world", knower_id=None, predicate="location",
              object_text="", object_entity_id=None, end_book=None):
    start = content.index(phrase)
    return canon.propose_fact(
        series_id, subject["id"], predicate, object_text=object_text,
        object_entity_id=object_entity_id,
        scope=scope, knower_id=knower_id,
        start_book=book, end_book=end_book,
        source_id=sources[0]["id"], quote_start=start,
        quote_end=start + len(phrase), quote=phrase,
    )


def test_imports_are_author_confirmed_and_source_snapshots_immutable(series_fixture):
    series_id, books, first, _ = series_fixture
    with pytest.raises(ValueError, match="Confirm"):
        vault.import_volume(series_id, "secret.md", b"Private book", 3,
                            title=None, kind="novel", edition_status="draft",
                            rights_confirmed=False)
    sources = vault.volume_sources(series_id, books[0]["id"])
    info, text = vault.source_text(series_id, sources[0]["id"])
    assert first == text
    assert info["ordinal"] == 1
    assert books[0]["edition_status"] == "published"
    with pytest.raises(ValueError):
        vault.import_volume(series_id, "../escape.md", b"secret", 3,
                            title=None, kind="novel", edition_status="draft",
                            rights_confirmed=True)


def test_attach_existing_project_is_read_only_and_stale_is_visible(
    series_fixture,
):
    series_id, _, _, _ = series_fixture
    project = storage.create_project("My Separate Book")
    slug = project["slug"]
    original = storage.read_text(slug, "manuscript/chapter-001.md")
    vault.attach_project(series_id, slug, 3, title="Third Book",
                         kind="novel", edition_status="draft",
                         rights_confirmed=True)
    assert storage.read_text(slug, "manuscript/chapter-001.md") == original
    third = vault.series_detail(series_id)["volumes"][2]
    sources = vault.volume_sources(series_id, third["id"])
    assert not sources[0]["linked_project_changed"]
    storage.save_text(slug, "manuscript/chapter-001.md", original + "A revision.")
    assert vault.volume_sources(series_id, third["id"])[0]["linked_project_changed"]
    _, evidence = vault.source_text(series_id, sources[0]["id"])
    assert evidence == original  # citation never quietly shifts to new prose


def test_non_destructive_proposal_approval_and_temporal_spoiler_scoping(series_fixture):
    series_id, books, first, second = series_fixture
    moon = canon.add_entity(series_id, "Moon Key", "artifact", aliases=["the key"])
    lyra = canon.add_entity(series_id, "Lyra", "character")
    src1 = books[0]["sources"]
    src2 = books[1]["sources"]
    key = "Lyra placed the Moon Key in the glass vault."
    old = _add_fact(series_id, src1, lyra, moon, first, key, 1,
                    predicate="located_in", object_text="glass vault", end_book=1)
    assert old["status"] == "proposed"
    assert canon.at_book(series_id, 1)["facts"] == []
    canon.review_fact(series_id, old["id"], "approved")
    state1 = canon.at_book(series_id, 1)
    assert len(state1["facts"]) == 1
    assert state1["facts"][0]["reference"]["quote"] == key
    assert state1["facts"][0]["reference"]["book"] == 1
    new_phrase = "Lyra moved the Moon Key to the sunlit tower."
    new = _add_fact(series_id, src2, lyra, moon, second, new_phrase, 2,
                    predicate="located_in", object_text="sunlit tower")
    canon.review_fact(series_id, new["id"], "approved")
    assert [item["object_text"] for item in canon.at_book(series_id, 1)["facts"]] == [
        "glass vault"]
    assert [item["object_text"] for item in canon.at_book(series_id, 2)["facts"]] == [
        "sunlit tower"]
    response = canon.ask_temporal(series_id, "Where is the Moon Key?", 1)
    assert "glass vault" in response["answer"]
    assert "sunlit tower" not in response["answer"]
    assert response["sources"][0]["quote"] == key
    assert response["evidence_only"] is True
    with pytest.raises(ValueError, match="immutable"):
        canon.review_fact(series_id, old["id"], "rejected")


def test_character_belief_and_reader_reveal_are_independent(series_fixture):
    series_id, books, first, _ = series_fixture
    moon = canon.add_entity(series_id, "Moon Key", "artifact")
    lyra = canon.add_entity(series_id, "Lyra", "character")
    belief_phrase = "Lyra believes the key is harmless."
    belief = _add_fact(series_id, books[0]["sources"], lyra, moon, first,
                       belief_phrase, 1, scope="character_belief",
                       knower_id=lyra["id"], predicate="believes_harmless",
                       object_text="yes")
    reveal_phrase = "Readers learn the key opens the sealed gate."
    reveal = _add_fact(series_id, books[0]["sources"], lyra, moon, first,
                       reveal_phrase, 1, scope="reader_reveal",
                       predicate="opens", object_text="sealed gate")
    canon.review_fact(series_id, belief["id"], "approved")
    canon.review_fact(series_id, reveal["id"], "approved")
    assert not canon.at_book(series_id, 1, scope="world")["facts"]
    assert len(canon.at_book(series_id, 1, scope="character_belief",
                             knower_id=lyra["id"])["facts"]) == 1
    assert len(canon.at_book(series_id, 1, scope="reader_reveal")["facts"]) == 1
    with pytest.raises(ValueError, match="knowledge"):
        canon.at_book(series_id, 1, scope="character_belief")
    with pytest.raises(ValueError, match="character"):
        canon.propose_fact(
            series_id, moon["id"], "knows", object_text="secret",
            scope="character_belief", knower_id=moon["id"],
            start_book=1, source_id=books[0]["sources"][0]["id"],
            quote_start=first.index(belief_phrase),
            quote_end=first.index(belief_phrase) + len(belief_phrase),
            quote=belief_phrase)


def test_exact_source_validation_conflicts_and_timeline(series_fixture):
    series_id, books, first, _ = series_fixture
    moon = canon.add_entity(series_id, "Moon Key", "artifact")
    lyra = canon.add_entity(series_id, "Lyra", "character")
    phrase = "Lyra placed the Moon Key in the glass vault."
    valid = _add_fact(series_id, books[0]["sources"], lyra, moon, first, phrase, 1,
                      predicate="located_in", object_text="glass vault")
    contradictory = _add_fact(series_id, books[0]["sources"], lyra, moon, first,
                              phrase, 1, predicate="located_in", object_text="forest")
    for row in (valid, contradictory):
        canon.review_fact(series_id, row["id"], "approved")
    state = canon.at_book(series_id, 1)
    assert len(state["conflicts"]) == 1
    assert len(canon.timeline(series_id)["events"]) == 2
    with pytest.raises(ValueError, match="quoted"):
        canon.propose_fact(
            series_id, moon["id"], "located_in", object_text="ocean",
            start_book=1, source_id=books[0]["sources"][0]["id"],
            quote_start=0, quote_end=5, quote="BROKEN")


def test_import_docx_and_api_rights_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    doc = Document()
    doc.add_paragraph("The northern keep collapsed at midnight.")
    contents = io.BytesIO()
    doc.save(contents)
    with TestClient(app) as client:
        created = client.post("/api/series", json={"title": "Northern Saga"})
        assert created.status_code == 201
        series_id = created.json()["id"]
        files = {"file": ("book-one.docx", contents.getvalue(),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        denied = client.post(
            f"/api/series/{series_id}/volumes/import",
            data={"ordinal": "1", "rights_confirmed": "false"}, files=files)
        assert denied.status_code == 400
        result = client.post(
            f"/api/series/{series_id}/volumes/import",
            data={"ordinal": "1", "title": "Northern Saga I",
                  "rights_confirmed": "true"}, files=files)
        assert result.status_code == 201, result.text
        sources = result.json()["volumes"][0]["sources"]
        excerpt = client.get(
            f"/api/series/{series_id}/sources/{sources[0]['id']}/excerpt",
            params={"query": "midnight"})
        assert excerpt.status_code == 200
        assert "midnight" in excerpt.json()["excerpt"]


def test_temporal_queries_cannot_leak_future_books(series_fixture):
    series_id, books, first, second = series_fixture
    moon = canon.add_entity(series_id, "Moon Key", "artifact")
    phrase = "Lyra moved the Moon Key to the sunlit tower."
    later = _add_fact(series_id, books[1]["sources"], None, moon, second, phrase, 2,
                      predicate="located_in", object_text="sunlit tower")
    canon.review_fact(series_id, later["id"], "approved")
    with pytest.raises(ValueError, match="before the book"):
        _add_fact(series_id, books[1]["sources"], None, moon, second, phrase, 1,
                  predicate="located_in", object_text="future spoiler")
    assert not canon.at_book(series_id, 1)["facts"]
    assert canon.ask_temporal(series_id, "Where is the Moon Key?", 1)["sources"] == []
