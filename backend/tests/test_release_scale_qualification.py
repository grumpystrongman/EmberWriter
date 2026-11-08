"""Large-scale, *synthetic* author-workflow tests, NOT artistic or audio sign-off.

Exercises real book-drafting and publication paths at 60k+ words and 20
chapters. The prose generator and neural waveform generator are STUBS, so
this test must never be used as the human novel/audiobook release gate.
"""
from __future__ import annotations

import hashlib
import re
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from docx import Document
from ebooklib import ITEM_DOCUMENT, epub

from app import audio_production, book_studio, kokoro_book, publishing, recovery_vault, storage
from app.models import ProviderConfig

CHAPTERS = 20
TARGET_WORDS = 3100


def _synthetic_chapter(index: int) -> str:
    """Nonliterary synthetic load, deliberately recognizable as QA data."""
    paragraphs = []
    for segment in range(155):
        paragraphs.append(
            f"Scene {index:02d} checkpoint {segment:03d}. "
            + " ".join(
                f"placeholder{i % 13} lantern_{index:02d} "
                f"event_{segment:03d} evidence_{i:03d}"
                for i in range(5)
            )
            + "."
        )
    return "\n\n".join(paragraphs)


@pytest.fixture
def long_book(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "author-library" / "projects")
    slug = storage.create_project("RELEASE QA Synthetic 20 Chapter Novel")["slug"]
    book_studio.configure(
        slug, premise="A synthetic archive of invented checkpoints.",
        voice="Synthetic QA text only. Not a creative work.",
        chapters=[
            {"title": f"Chapter {i:02d} Test Data", "brief": f"QA volume segment {i}"}
            for i in range(1, CHAPTERS + 1)
        ],
        target_words=TARGET_WORDS,
    )
    return slug, tmp_path


@pytest.mark.asyncio
async def test_sixty_thousand_word_book_drafts_are_never_auto_approved_and_exports_match(long_book):
    slug, temp = long_book
    call = 0
    model = ProviderConfig(provider="ollama", model="synthetic-test-stub",
                           base_url="http://127.0.0.1:11434")

    async def synthesize(*_args, **_kwargs):
        nonlocal call
        call += 1
        return _synthetic_chapter(call)

    with patch("app.book_studio.generate_complete_prose", side_effect=synthesize):
        for number in range(1, CHAPTERS + 1):
            result = await book_studio.draft_next(slug, model)
            assert result["chapter"]["number"] == number
            assert book_studio.load_state(slug)["chapters"][number - 1]["status"] == "candidate"
            assert not (storage.project_root(slug)
                        / f"manuscript/book-studio/chapter-{number:03d}.md").exists()
    assert call == CHAPTERS
    state = book_studio.load_state(slug)
    assert len(state["chapters"]) == CHAPTERS
    assert all(c["status"] == "candidate" for c in state["chapters"])

    # A test harness explicitly *simulates* an author clicking Approve; not
    # editorial acceptance of the generated 60k-word synthetic load.
    for index in range(1, CHAPTERS + 1):
        book_studio.approve(slug, index)
    state = book_studio.load_state(slug)
    assert all(c["status"] == "approved" for c in state["chapters"])
    documents = publishing.compiled_documents(slug)
    assert len(documents) == CHAPTERS
    assert (storage.project_root(slug) / "manuscript/chapter-001.md").exists()
    assert [item["title"] for item in documents] == [
        f"Chapter {i:02d} Test Data" for i in range(1, CHAPTERS + 1)
    ]
    word_count = sum(len(re.findall(r"\b[\w'-]+\b", item["content"]))
                     for item in documents)
    assert word_count >= 60_000
    source_hashes = {
        item["path"]: hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
        for item in documents
    }
    assert len(set(source_hashes.values())) == CHAPTERS

    epub_path = temp / "synthetic-release.epub"
    docx_path = temp / "synthetic-release.docx"
    publishing.export_epub(epub_path, title="Synthetic Quality Test", author="Test Fixture",
                           language="en", documents=documents, include_toc=True)
    publishing.export_docx(docx_path, title="Synthetic Quality Test",
                           author="Test Fixture", documents=documents)
    digital = epub.read_epub(str(epub_path))
    chapters = [item for item in digital.get_items()
                if item.get_type() == ITEM_DOCUMENT
                and item.file_name.startswith("chapter-")]
    assert len(chapters) == CHAPTERS
    for index, chapter in enumerate(sorted(chapters, key=lambda item: item.file_name), 1):
        assert f"Scene {index:02d} checkpoint 000" in chapter.get_content().decode("utf-8")
    word_doc = Document(docx_path)
    all_text = "\n".join(paragraph.text for paragraph in word_doc.paragraphs)
    for index in range(1, CHAPTERS + 1):
        assert f"Scene {index:02d} checkpoint 000" in all_text
    # Provenance from the compiled edition remains byte-for-byte unchanged.
    for item in documents:
        assert hashlib.sha256(storage.read_text(slug, item["path"]).encode()).hexdigest() == (
            source_hashes[item["path"]]
        )
    # Explicitly state what this fixture cannot prove.
    assert "Synthetic" in storage.get_project(slug)["name"]


@pytest.mark.asyncio
async def test_twenty_chapter_neural_queue_maintains_provenance_and_author_gate(long_book):
    slug, _temp = long_book
    # The test uses real manuscript files and real queue/assembly logic; it
    # simulates only the costly speech model. It DOES NOT produce speech.
    for index in range(1, CHAPTERS + 1):
        storage.save_text(
            slug, f"manuscript/book-studio/chapter-{index:03d}.md",
            f"# Chapter {index:02d} Test Data\n\n" + _synthetic_chapter(index),
        )
    from app.binder import sync_binder
    sync_binder(slug)
    cast = audio_production.load(slug)
    cast["kokoro_voices"] = {"Narrator": {"voice_id": "af_heart", "speed": 1.0}}
    audio_production._write(slug, cast)
    with patch("app.kokoro_book.kokoro_local.status",
               return_value={"installed": True, "voice_ids": ["af_heart"]}):
        started = kokoro_book.start(slug)
        job = kokoro_book._read(slug)
        assert len(job["chapters"]) == CHAPTERS
        assert all(ch["path"] != "manuscript/chapter-001.md" for ch in job["chapters"])
        assert started["completed"] == 0
        assert len(job["chunks"]) > 1000
        assert not started["publication_approved"]
        first = job["chapters"][0]
        assert first["source_sha256"] == hashlib.sha256(
            storage.read_text(slug, first["path"]).encode()).hexdigest()
        for index, chunk in enumerate(job["chunks"]):
            target = kokoro_book._part_path(slug, job["id"], index)
            target.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(target), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24000)
                output.writeframes(bytes(480))
            chunk["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            chunk["status"] = "rendered"
        kokoro_book._atomic_json(kokoro_book._jobfile(slug), job)
        with patch("app.kokoro_book._render_part",
                   side_effect=AssertionError("must reuse all verified audio fragments")):
            completed = await kokoro_book.advance(slug)
        assert completed["status"] == "completed"
        assert completed["completed"] == completed["total"]
        assert all(ch["status"] == "rendered_unapproved" for ch in completed["chapters"])
        assert not completed["publication_approved"]
        for chapter in completed["chapters"]:
            recording = kokoro_book.chapter_audio(slug, chapter["filename"])
            with wave.open(str(recording), "rb") as output:
                assert output.getnframes() > 0
                assert output.getframerate() == 24000
        # Changing one character in source invalidates approval/currentness.
        path = completed["chapters"][0]["path"]
        storage.save_text(slug, path, storage.read_text(slug, path) + "\nEdit after audio.")
        assert kokoro_book.status(slug)["stale"]
        with pytest.raises(ValueError, match="manuscript changed"):
            kokoro_book.chapter_audio(slug, completed["chapters"][0]["filename"])



def test_original_author_edited_starter_chapter_is_never_silently_excluded(long_book):
    slug, _ = long_book
    original = storage.read_text(slug, "manuscript/chapter-001.md")
    assert "Begin " in original
    from app.binder import sync_binder

    storage.save_text(slug, "manuscript/book-studio/chapter-001.md",
                      "# Actual Book Studio Chapter\n\nThis is a drafted chapter.")
    sync_binder(slug)
    paths = [item["path"] for item in publishing.compiled_documents(slug)]
    assert "manuscript/chapter-001.md" not in paths
    assert "manuscript/book-studio/chapter-001.md" in paths
    storage.save_text(slug, "manuscript/chapter-001.md",
                      original + "\nThe author consciously wrote a new paragraph.")
    sync_binder(slug)
    paths = [item["path"] for item in publishing.compiled_documents(slug)]
    assert "manuscript/chapter-001.md" in paths
    assert "manuscript/book-studio/chapter-001.md" in paths



def test_full_synthetic_series_with_audio_media_mirrors_and_recovers_without_rewrite(
    long_book,
):
    slug, temp = long_book
    for index in range(1, CHAPTERS + 1):
        storage.save_text(
            slug, f"manuscript/book-studio/chapter-{index:03d}.md",
            f"# Chapter {index:02d} Test Data\n\n" + _synthetic_chapter(index),
        )
    from app.binder import sync_binder

    sync_binder(slug)
    library = storage.PROJECTS_ROOT.parent
    binary = library / "assets" / "voice rehearsal.wav"
    binary.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(binary), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(bytes(48000))
    source_path = "manuscript/book-studio/chapter-010.md"
    original = storage.read_text(slug, source_path)
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()

    recovery_vault.configure(
        str(temp / "separate backup store"),
        mirror_directory=str(temp / "separate mirrored store"),
    )
    generation = recovery_vault.create_backup("full book with audio QA")
    assert generation["verified"]
    assert generation["mirror_healthy"]
    assert recovery_vault.verify(generation["id"])["healthy"]
    storage.save_text(slug, source_path, original + "\nAuthor-simulated correction.")
    destination = temp / "verified old edition"
    result = recovery_vault.restore(generation["id"], destination=str(destination))
    assert not result["current_library_changed"]
    restored = (
        destination / "projects" / slug / source_path
    )
    assert hashlib.sha256(restored.read_bytes()).hexdigest() == digest
    assert (
        destination / "assets" / "voice rehearsal.wav"
    ).read_bytes() == binary.read_bytes()
    assert "correction" in storage.read_text(slug, source_path)
    # Independent mirror is a separate recovery source; the original data
    # directory remains untouched even when switching to that copy.
    recovery_vault.configure(str(temp / "separate mirrored store"), automatic=False)
    mirrored = recovery_vault.restore(
        generation["id"], destination=str(temp / "restored from independent mirror")
    )
    assert not mirrored["current_library_changed"]
    assert hashlib.sha256(
        (
            Path(mirrored["directory"]) / "projects" / slug / source_path
        ).read_bytes()
    ).hexdigest() == digest


def test_atomic_manuscript_write_preserves_exact_utf8_lf_bytes_on_windows(long_book):
    slug, _ = long_book
    path = "manuscript/chapter-001.md"
    material = "# LF Proof\n\nFirst scene.\nSecond scene.\n"
    storage.save_text(slug, path, material)
    saved = storage.project_root(slug) / path
    assert saved.read_bytes() == material.encode("utf-8")
    assert storage.read_text(slug, path) == material
    assert b"\r\n" not in saved.read_bytes()
