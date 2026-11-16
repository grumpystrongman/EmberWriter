"""EPUB table-of-contents fragments must map to exact immutable text offsets."""
from __future__ import annotations

import io

import pytest
from ebooklib import epub

from app import series_epub_index as index
from app import series_epub_structure as structure
from app import series_vault as vault
from app import storage


def make_epub(*, changed: bool = False) -> bytes:
    book = epub.EpubBook()
    book.set_identifier("fictional-anchored-toc")
    book.set_title("Fictional Chapters")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Section", file_name="chap.xhtml", lang="en")
    chapter.content = (
        "<html><body><p>Front matter about red foxes.</p>"
        '<h2 id="one">Chapter One</h2><p>The fictional map is blue.</p>'
        '<a id="between"></a><p>A quiet transition marks the threshold.</p>'
        '<h2 id="two">Chapter Two</h2><p>'
        + ("The map is green." if changed else "The map is still blue.")
        + '</p><h3 id="duplicate">Echo</h3><h3 id="duplicate">Echo</h3>'
        "</body></html>"
    )
    book.add_item(chapter)
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    book.toc = (
        epub.Link("chap.xhtml#one", "First chapter in ToC", "first"),
        (
            epub.Section("Nested chapter"),
            [
                epub.Link("chap.xhtml#between", "A linked transition", "middle"),
                epub.Link("chap.xhtml#two", "Second chapter in ToC", "second"),
            ],
        ),
        epub.Link("chap.xhtml#duplicate", "Ambiguous duplicate", "duplicate"),
        epub.Link("https://untrusted.example/chapter.xhtml#one", "Remote link", "remote"),
        epub.Link("unknown.xhtml#one", "Unknown file", "unknown"),
    )
    memory = io.BytesIO()
    epub.write_epub(memory, book)
    return memory.getvalue()


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Exact ToC Test")["id"]
    epub_bytes = make_epub()
    detail = vault.import_volume(
        sid, "book.epub", epub_bytes, 1, title="Book",
        kind="novel", edition_status="reference", rights_confirmed=True,
    )
    source_id = detail["volumes"][0]["sources"][0]["id"]
    return sid, source_id, epub_bytes


def test_nested_toc_anchors_resolve_without_searching_repeated_prose(sample):
    sid, source_id, epub_bytes = sample
    before, content = vault.source_text(sid, source_id)
    report = structure.preview(sid, source_id, epub_bytes)
    assert report["exact_snapshot_match"]
    assert report["spine_sections"] >= 1  # EPUB nav document may be a spine item
    assert report["toc_fragment_sections"] == 3
    assert report["matched_sections"] == report["spine_sections"] + 3
    assert not report["story_sequence_inferred"]
    anchors = [item for item in report["sections"]
               if item["confidence"] == "exact_epub_toc_fragment"]
    assert [item["title"] for item in anchors] == [
        "First chapter in ToC", "A linked transition", "Second chapter in ToC",
    ]
    assert [content[item["start"]:item["start"]+len(value)] for item,value in zip(
        anchors, ("Chapter One", "A quiet transition", "Chapter Two"), strict=True
    )] == ["Chapter One", "A quiet transition", "Chapter Two"]
    assert all(item["end"] > item["start"] for item in anchors)
    assert anchors[0]["end"] == anchors[1]["start"]
    assert anchors[1]["end"] == anchors[2]["start"]
    assert index.read(sid, source_id) is None

    saved = index.save(sid, source_id, epub_bytes)
    assert saved["saved"] is True
    recovered = index.read(sid, source_id)
    assert len(recovered["sections"]) == report["matched_sections"]
    assert not recovered["story_sequence_inferred"]
    after, unchanged = vault.source_text(sid, source_id)
    assert after["sha256"] == before["sha256"] and unchanged == content


def test_different_edition_returns_no_spine_or_toc_positions(sample):
    sid, source_id, _ = sample
    result = structure.preview(sid, source_id, make_epub(changed=True))
    assert result["status"] == "edition_mismatch"
    assert result["sections"] == []
    assert not result["exact_snapshot_match"]


def test_saved_toc_position_preferred_over_overlapping_spine(sample):
    from fastapi.testclient import TestClient

    from app import series_extraction_jobs as jobs
    from app.main import app

    sid, source_id, original = sample
    report = structure.preview(sid, source_id, original)
    target = next(item for item in report["sections"]
                  if item.get("toc_fragment") == "two")
    index.save(sid, source_id, original)
    with TestClient(app) as client:
        response = client.get(
            f"/api/series/{sid}/sources/{source_id}/sections",
            params={"position": target["start"] + 1},
        )
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["structure_index_saved"] is True
        assert value["selected_section"] == target["index"]
        assert any(row.get("toc_fragment") == "two" for row in value["sections"])

    _, content = vault.source_text(sid, source_id)
    start = target["start"] - 3
    stop, alignment = jobs._plan_window(sid, source_id, content, start)
    assert stop == target["start"]
    assert alignment == "author_confirmed_epub_spine"
