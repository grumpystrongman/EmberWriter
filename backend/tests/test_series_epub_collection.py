"""Chunk 4 local-only multi-book EPUB index recovery (synthetic sources)."""
from __future__ import annotations

import io
import zipfile

import pytest
from ebooklib import epub
from fastapi.testclient import TestClient

from app import series_bulk_import, series_epub_collection, series_epub_index, storage
from app import series_vault as vault
from app.main import app


def make_epub(label: str) -> bytes:
    book = epub.EpubBook()
    book.set_identifier("fictional-" + label.lower().replace(" ", "-"))
    book.set_title(label)
    book.set_language("en")
    for index in (1, 2):
        part = epub.EpubHtml(title=f"Chapter {index}", file_name=f"part{index}.xhtml", lang="en")
        part.content = f"<html><body><h1>Chapter {index}</h1><p>{label} crossed a synthetic mountain at noon {index}.</p></body></html>"
        book.add_item(part)
        if index == 1:
            first = part
        else:
            second = part
    book.add_item(epub.EpubNav())
    book.spine = ["nav", first, second]
    book.toc = (first, second)
    buffer = io.BytesIO()
    epub.write_epub(buffer, book)
    return buffer.getvalue()


def archive(contents: list[tuple[str, bytes]]) -> bytes:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, blob in contents:
            z.writestr(name, blob)
    return memory.getvalue()


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Fictional Cycling")["id"]
    contents = [
        ("Cycle 001 - First.epub", make_epub("First")),
        ("Cycle 002 - Second.epub", make_epub("Second")),
    ]
    original = archive(contents)
    series_bulk_import.import_epub_zip(sid, original, rights_confirmed=True)
    sources = [
        item["sources"][0]["id"] for item in vault.series_detail(sid)["volumes"]
    ]
    return sid, sources, contents, original


def test_collection_preview_is_read_only_and_confirmation_atomic(sample):
    sid, sources, _, original = sample
    source_texts = [vault.source_text(sid, source)[1] for source in sources]
    before = [series_epub_index.read(sid, source) for source in sources]
    assert before == [None, None]

    preview = series_epub_collection.preview(sid, original)
    assert preview["books_in_archive"] == 2
    assert preview["matched_books"] == 2
    assert preview["unmatched_books"] == 0
    assert preview["recoverable_sections"] >= 4
    assert preview["can_confirm"] and not preview["saved"]
    assert [series_epub_index.read(sid, source) for source in sources] == before

    result = series_epub_collection.confirm(sid, original)
    assert result["saved"] and result["indexed_books"] == 2
    assert not result["source_text_changed"]
    assert not result["canon_approved"]
    assert not result["story_sequence_inferred"]
    for source, text in zip(sources, source_texts, strict=True):
        saved = series_epub_index.read(sid, source)
        assert saved is not None
        assert len(saved["sections"]) >= 2
        assert vault.source_text(sid, source)[1] == text


def test_mismatched_book_blocks_every_index(sample):
    sid, sources, contents, _original = sample
    broken = archive([contents[0], (contents[1][0], make_epub("Other Edition"))])
    preview = series_epub_collection.preview(sid, broken)
    assert preview["matched_books"] == 1
    assert preview["unmatched_books"] == 1
    assert not preview["can_confirm"]
    with pytest.raises(ValueError, match="unmatched EPUBs"):
        series_epub_collection.confirm(sid, broken)
    assert all(series_epub_index.read(sid, source) is None for source in sources)


def test_missing_source_and_unsafe_member_are_not_indexed(sample):
    sid, sources, contents, _ = sample
    wrong_name = archive([(contents[0][0].replace("First", "Another"), contents[0][1])])
    preview = series_epub_collection.preview(sid, wrong_name)
    assert preview["matched_books"] == 0
    assert not preview["can_confirm"]
    assert preview["books"][0]["status"] == "source_not_found"
    with pytest.raises(ValueError):
        series_epub_collection.confirm(sid, wrong_name)
    unsafe = archive([("../Cycle 001 - First.epub", contents[0][1])])
    with pytest.raises(ValueError, match="unsafe path"):
        series_epub_collection.preview(sid, unsafe)
    assert series_epub_index.read(sid, sources[0]) is None


def test_collection_api_requires_author_confirm_and_isolation(sample):
    sid, sources, _, original = sample
    foreign = vault.create_series("Separate private project")["id"]
    with TestClient(app) as client:
        uri = f"/api/series/{sid}/epub-structure-zip-"
        preview = client.post(
            uri + "preview", files={"file": ("volumes.zip", original, "application/zip")},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["can_confirm"]
        assert series_epub_index.read(sid, sources[0]) is None
        denied = client.post(
            f"/api/series/{foreign}/epub-structure-zip-confirm",
            files={"file": ("volumes.zip", original, "application/zip")},
        )
        assert denied.status_code == 400
        assert series_epub_index.read(sid, sources[0]) is None
        confirm = client.post(
            uri + "confirm", files={"file": ("volumes.zip", original, "application/zip")},
        )
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["indexed_books"] == 2
        assert series_epub_index.read(sid, sources[0]) is not None
