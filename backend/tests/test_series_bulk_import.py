"""Synthetic bulk-EPUB ingestion and isolation tests; no copyrighted text fixtures."""
from __future__ import annotations

import io
import zipfile

import pytest
from ebooklib import epub
from fastapi.testclient import TestClient

from app import series_bulk_import, series_vault, storage
from app.main import app


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    first = series_vault.create_series("Synthetic Starship Cycle")
    second = series_vault.create_series("Other Author's Series")
    return first["id"], second["id"]


def _epub(title: str) -> bytes:
    book = epub.EpubBook()
    book.set_identifier("synthetic-" + title.lower().replace(" ", "-"))
    book.set_title(title)
    book.set_language("en")
    chapter = epub.EpubHtml(title="First Chapter", file_name="one.xhtml", lang="en")
    chapter.content = (
        "<html><body><h1>First Chapter</h1><p>"
        + title + " started by the moon and discovered an old chart.</p></body></html>"
    )
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNav())
    output = io.BytesIO()
    epub.write_epub(output, book)
    return output.getvalue()


def _zip(members: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in members:
            archive.writestr(filename, content)
    return output.getvalue()


def test_numbered_zip_preserves_order_and_source_provenance(isolated):
    series_id, other_id = isolated
    data = _zip([
        ("Cycle Collection/CredDB.CEF", b"irrelevant catalog metadata"),
        ("Cycle Collection/Cycle 003 - Third Journey.epub", _epub("Third Journey")),
        ("Cycle Collection/Cycle 001 - First Journey.epub", _epub("First Journey")),
        ("Cycle Collection/Cycle 002 - Second Journey.epub", _epub("Second Journey")),
    ])
    result = series_bulk_import.import_epub_zip(
        series_id, data, rights_confirmed=True
    )
    assert result["imported_count"] == 3
    assert result["book_orders"] == [1, 2, 3]
    assert result["ignored_non_epub"] == 1
    assert result["canon_facts_approved"] == 0
    details = series_vault.series_detail(series_id)
    assert [row["ordinal"] for row in details["volumes"]] == [1, 2, 3]
    assert all(row["edition_status"] == "reference" for row in details["volumes"])
    assert all(row["source_count"] == 1 for row in details["volumes"])
    assert not series_vault.series_detail(other_id)["volumes"]
    source = details["volumes"][0]["sources"][0]
    _, text = series_vault.source_text(series_id, source["id"])
    assert "First Journey started by the moon" in text
    assert "Third Journey" not in text


def test_unauthorized_duplicate_malformed_archives_do_not_mutate_series(isolated):
    series_id, _ = isolated
    good = _zip([("Cycle 001 - First.epub", _epub("First"))])
    with pytest.raises(ValueError, match="Confirm permission"):
        series_bulk_import.import_epub_zip(series_id, good, rights_confirmed=False)
    with pytest.raises(ValueError, match="ZIP"):
        series_bulk_import.import_epub_zip(series_id, b"not a zip", rights_confirmed=True)
    duplicate = _zip([
        ("Cycle 001 - First.epub", _epub("First")),
        ("Cycle 001 - Again.epub", _epub("Again")),
    ])
    with pytest.raises(ValueError, match="Duplicate"):
        series_bulk_import.import_epub_zip(series_id, duplicate, rights_confirmed=True)
    invalid = _zip([
        ("Cycle 001 - First.epub", _epub("First")),
        ("Cycle 002 - Missing.epub", b"invalid ePub bytes"),
    ])
    with pytest.raises((ValueError, OSError, zipfile.BadZipFile, KeyError)):
        series_bulk_import.import_epub_zip(series_id, invalid, rights_confirmed=True)
    assert not series_vault.series_detail(series_id)["volumes"]


def test_zip_path_traversal_rejected(isolated):
    series_id, _ = isolated
    unsafe = _zip([("../Cycle 001 - First.epub", _epub("First"))])
    with pytest.raises(ValueError, match="unsafe path"):
        series_bulk_import.import_epub_zip(series_id, unsafe, rights_confirmed=True)


def test_overlap_existing_ordinals_rejected_without_changes(isolated):
    series_id, _ = isolated
    good = _zip([("Cycle 001 - First.epub", _epub("First"))])
    series_bulk_import.import_epub_zip(series_id, good, rights_confirmed=True)
    with pytest.raises(ValueError, match="already exist"):
        series_bulk_import.import_epub_zip(series_id, good, rights_confirmed=True)
    assert len(series_vault.series_detail(series_id)["volumes"]) == 1


def test_bulk_upload_endpoint_and_safe_boolean_contract(isolated):
    series_id, _ = isolated
    payload = _zip([("Cycle 001 - First.epub", _epub("First"))])
    with TestClient(app) as client:
        url = f"/api/series/{series_id}/volumes/bulk-zip"
        denied = client.post(url, files={"file": ("books.zip", payload, "application/zip")},
                             data={"rights_confirmed": "false"})
        assert denied.status_code == 400
        accepted = client.post(url, files={"file": ("books.zip", payload, "application/zip")},
                               data={"rights_confirmed": "true"})
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["book_orders"] == [1]
        assert len(client.get(f"/api/series/{series_id}").json()["volumes"]) == 1


def test_windows_newline_roundtrip_is_byte_identical(isolated):
    import hashlib

    sample = "Chapter One\r\nLine with CRLF.\rOld Mac ending.\nNormal line."
    volume_id = "a" * 32
    source_id = "b" * 32
    snapshot_path = series_vault._snapshot(volume_id, source_id, sample)
    file_path = series_vault._root() / snapshot_path
    assert file_path.read_bytes() == sample.encode("utf-8")
    assert hashlib.sha256(file_path.read_bytes()).hexdigest() == hashlib.sha256(
        sample.encode("utf-8")
    ).hexdigest()


def test_legacy_epub_soft_hyphen_does_not_hide_character_names():
    from app import series_vault

    raw = _epub("Re\u00admo Chi\u00adun")
    text = series_vault._source_text(raw, "Tale 001 - Names.epub")
    assert "Remo Chiun" in text
    assert "\u00ad" not in text
    assert "\u200b" not in text


def test_nested_epub_expansion_bomb_is_rejected_before_parsing(isolated):
    series_id, _ = isolated
    interior = io.BytesIO()
    with zipfile.ZipFile(interior, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr("OEBPS/massive.xhtml", "X" * (17 * 1024 * 1024))
    outer = _zip([("Cycle 001 - Suspicious.epub", interior.getvalue())])
    with pytest.raises(ValueError, match="oversized internal content"):
        series_bulk_import.import_epub_zip(series_id, outer, rights_confirmed=True)
    assert not series_vault.series_detail(series_id)["volumes"]


def test_nested_epub_path_traversal_and_missing_mimetype_are_rejected(isolated):
    series_id, _ = isolated
    for inner_files, error in [
        ([("../escape.xhtml", "<p>unsafe</p>")], "unsafe inner path"),
        ([("OPS/text.xhtml", "<p>missing mimetype</p>")], "missing mimetype"),
    ]:
        interior = io.BytesIO()
        with zipfile.ZipFile(interior, "w", zipfile.ZIP_DEFLATED) as book:
            if "missing" not in error:
                book.writestr("mimetype", "application/epub+zip")
            for name, content in inner_files:
                book.writestr(name, content)
        outer = _zip([("Cycle 001 - Suspicious.epub", interior.getvalue())])
        with pytest.raises(ValueError, match=error):
            series_bulk_import.import_epub_zip(series_id, outer,
                                              rights_confirmed=True)
        assert not series_vault.series_detail(series_id)["volumes"]


def test_epub_mimetype_bomb_and_duplicate_mimetype_rejected_before_import(isolated):
    series_id, _ = isolated
    # A valid-looking ZIP with an oversized mimetype should be rejected on
    # metadata alone, rather than decompressing attacker-controlled contents.
    for members in (
        [("mimetype", b"A" * 2_000_000)],
        [("mimetype", b"application/epub+zip"),
         ("mimetype", b"application/epub+zip")],
    ):
        interior = io.BytesIO()
        with zipfile.ZipFile(interior, "w", zipfile.ZIP_DEFLATED) as book:
            for name, payload in members:
                book.writestr(name, payload)
        outer = _zip([("Cycle 001 - Unsafe.epub", interior.getvalue())])
        with pytest.raises(ValueError, match="invalid or duplicate mimetype"):
            series_bulk_import.import_epub_zip(
                series_id, outer, rights_confirmed=True
            )
        assert series_vault.series_detail(series_id)["volumes"] == []
