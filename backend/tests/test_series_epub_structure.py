"""Chunk 4: exact EPUB-to-snapshot spine matching with no canon mutation."""
from __future__ import annotations

import io

import pytest
from ebooklib import epub
from fastapi.testclient import TestClient

from app import series_epub_structure, series_vault, storage
from app.main import app


def make_epub(text: str = "Mira opened the gate.") -> bytes:
    book = epub.EpubBook()
    book.set_identifier("synthetic-structure-test")
    book.set_title("Mira's Journey")
    book.set_language("en")
    first = epub.EpubHtml(title="One", file_name="first.xhtml", lang="en")
    first.content = "<html><body><p>Opening text about Mira.</p></body></html>"
    second = epub.EpubHtml(title="Two", file_name="second.xhtml", lang="en")
    second.content = f"<html><body><p>{text}</p></body></html>"
    book.add_item(first)
    book.add_item(second)
    book.toc = (first, second)
    book.spine = ["nav", first, second]
    book.add_item(epub.EpubNav())
    output = io.BytesIO()
    epub.write_epub(output, book)
    return output.getvalue()


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = series_vault.create_series("Synthetic Spine Proof")["id"]
    blob = make_epub()
    detail = series_vault.import_volume(
        sid, "book.epub", blob, 1, title="Mira", kind="novel",
        edition_status="reference", rights_confirmed=True,
    )
    src = detail["volumes"][0]["sources"][0]["id"]
    return sid, src, blob


def test_spine_matches_exact_snapshot_with_nonfictional_labels(source):
    sid, src, blob = source
    before, text = series_vault.source_text(sid, src)
    result = series_epub_structure.preview(sid, src, blob)
    assert result["exact_snapshot_match"] is True
    assert result["navigable"] is True
    assert result["story_sequence_inferred"] is False
    assert result["saved"] is False
    assert any(s["source_item"] == "second.xhtml" for s in result["sections"])
    for section in result["sections"]:
        assert text[section["start"]:section["end"]]
        assert section["author_confirmed"] is False
    after, unchanged = series_vault.source_text(sid, src)
    assert unchanged == text
    assert after["sha256"] == before["sha256"]


def test_other_edition_fails_closed_without_offsets(source):
    sid, src, _ = source
    result = series_epub_structure.preview(sid, src, make_epub("Mira refused the gate."))
    assert result["status"] == "edition_mismatch"
    assert result["sections"] == []
    assert not result["exact_snapshot_match"]


def test_preview_endpoint_and_series_isolation(source):
    sid, src, blob = source
    other = series_vault.create_series("Other Private Series")["id"]
    with TestClient(app) as client:
        response = client.post(
            f"/api/series/{sid}/sources/{src}/epub-structure-preview",
            files={"file": ("original.epub", blob, "application/epub+zip")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["exact_snapshot_match"] is True
        assert response.json()["saved"] is False
        denied = client.post(
            f"/api/series/{other}/sources/{src}/epub-structure-preview",
            files={"file": ("original.epub", blob, "application/epub+zip")},
        )
        assert denied.status_code == 404


def test_confirmed_metadata_persists_without_replacing_snapshot(source):
    sid, src, blob = source
    from app import series_epub_index
    _, text_before = series_vault.source_text(sid, src)
    assert series_epub_index.read(sid, src) is None
    with TestClient(app) as client:
        url = f"/api/series/{sid}/sources/{src}"
        approved = client.post(
            url + "/epub-structure-confirm",
            files={"file": ("original.epub", blob, "application/epub+zip")},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["saved"] is True
        indexed = client.get(url + "/sections")
        assert indexed.status_code == 200
        assert indexed.json()["structure_index_saved"] is True
        assert any(row["source_item"] == "second.xhtml" for row in indexed.json()["sections"])
        denied = client.post(
            url + "/epub-structure-confirm",
            files={"file": ("other.epub", make_epub("Wrong text"), "application/epub+zip")},
        )
        assert denied.status_code == 400
        still_indexed = client.get(url + "/sections")
        assert still_indexed.json()["sections"] == indexed.json()["sections"]
    _, text_after = series_vault.source_text(sid, src)
    assert text_after == text_before
    assert series_epub_index.read(sid, src)["story_sequence_inferred"] is False


def test_corrupt_epub_rejected(source):
    sid, src, _ = source
    with pytest.raises(ValueError):
        series_epub_structure.preview(sid, src, b"not an epub")
