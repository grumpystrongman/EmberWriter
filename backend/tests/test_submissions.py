from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfReader

from app import memory, storage, submissions
from app.models import ProviderConfig
from app.submission_models import SubmissionDestination, SubmissionProfile


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    project = storage.create_project("Submission Test")
    slug = project["slug"]
    storage.save_text(
        slug,
        "manuscript/chapter-001.md",
        "# Chapter 1\n\nMara crossed the silent station. She carried the key her brother died to protect.\n\n"
        "A voice called her name from the dark.\n" * 60,
    )
    return slug


def destination(**updates) -> SubmissionDestination:
    values = {
        "id": "agent-one",
        "name": "Agent One",
        "kind": "agent",
        "contact_name": "A. Agent",
        "email": "agent@example.test",
        "guidelines_url": "https://example.test/guidelines",
        "method": "email",
        "query_required": True,
        "synopsis_required": True,
        "sample_kind": "pages",
        "sample_count": 2,
        "attachment_mode": "body",
        "accepted_formats": ["docx", "pdf"],
        "expected_response_days": 30,
    }
    values.update(updates)
    return SubmissionDestination(**values)


def profile_for(slug: str, target: SubmissionDestination) -> SubmissionProfile:
    base = submissions.default_submission_profile(slug)
    return base.model_copy(
        update={
            "author_name": "A. Writer",
            "genre": "Adult Fantasy",
            "query_letter": (
                "Dear Agent,\n\nMara has one night to unlock the station.\n\n"
                "Sincerely,\nA. Writer"
            ),
            "synopsis": (
                "Mara enters the station, discovers the betrayal, survives the confrontation, "
                "and chooses to destroy the key."
            ),
            "bio": "A. Writer writes adult fantasy.",
            "destinations": [target],
        }
    )


def test_default_submission_profile_uses_compiled_manuscript(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)

    profile = submissions.default_submission_profile(slug)

    assert profile.title == "Submission Test"
    assert profile.word_count > 100
    assert profile.manuscript_preset == "standard_novel"


def test_destination_requirements_override_generic_preset(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    target = destination(sample_kind="chapters", sample_count=1, attachment_mode="attachments")
    profile = profile_for(slug, target).model_copy(update={"synopsis": ""})

    validation = submissions.validate_submission(slug, profile, target.id)

    assert validation.valid is False
    assert validation.sample_description.startswith("First 1 Binder")
    assert any(issue.code == "synopsis-required" for issue in validation.issues)


def test_page_sample_package_contains_exact_pdf_pages_body_and_manifest(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    target = destination(sample_count=2)
    profile = profile_for(slug, target)

    result, saved = submissions.build_submission_package(
        slug,
        profile=profile,
        destination_id=target.id,
    )
    root = storage.project_root(slug)
    zip_artifact = next(item for item in result.artifacts if item.format == "zip")
    archive_path = root / zip_artifact.relative_path

    assert result.validation.valid is True
    assert saved.records[-1].package_id == result.package_id
    assert saved.records[-1].status == "ready"
    assert saved.records[-1].follow_up_on == ""

    sample_pdf = root / next(
        item.relative_path
        for item in result.artifacts
        if item.filename == "sample-first-2-pages.pdf"
    )
    assert len(PdfReader(str(sample_pdf)).pages) == 2

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "query-letter.docx" in names
        assert "synopsis.docx" in names
        assert "sample-first-2-pages.pdf" in names
        assert "sample-first-2-pages.txt" in names
        assert "submission-body.txt" in names
        assert "submission-manifest.json" in names
        manifest = json.loads(archive.read("submission-manifest.json"))
        assert manifest["destination"]["id"] == target.id
        assert all(len(item["sha256"]) == 64 for item in manifest["files"])


def test_full_manuscript_docx_uses_submission_spacing_and_header(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    target = destination(
        sample_kind="full",
        sample_count=1,
        synopsis_required=False,
        attachment_mode="attachments",
    )
    profile = profile_for(slug, target)

    result, _ = submissions.build_submission_package(
        slug,
        profile=profile,
        destination_id=target.id,
    )
    root = storage.project_root(slug)
    sample = root / next(
        item.relative_path
        for item in result.artifacts
        if item.filename == "manuscript-sample.docx"
    )
    doc = Document(sample)

    assert doc.styles["Normal"].font.name == "Times New Roman"
    assert doc.styles["Normal"].paragraph_format.line_spacing == 2
    assert "Writer / SUBMISSION TEST" in doc.sections[0].header.paragraphs[0].text


def test_submission_record_starts_follow_up_clock_when_marked_sent(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    target = destination(synopsis_required=False, sample_kind="chapters", sample_count=1)
    profile = profile_for(slug, target)
    result, saved = submissions.build_submission_package(
        slug,
        profile=profile,
        destination_id=target.id,
    )
    record = saved.records[-1]

    assert record.follow_up_on == ""
    updated = submissions.update_submission_record(
        slug,
        saved,
        record.id,
        status="sent",
        submitted_at="2026-09-10",
        notes="Submitted through the agency form.",
    )

    current = next(item for item in updated.records if item.id == record.id)
    assert current.status == "sent"
    assert current.package_id == result.package_id
    assert current.submitted_at == "2026-09-10"
    assert current.follow_up_on == "2026-10-10"


def test_submission_context_rejects_stale_story_summary(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    old_content = storage.read_text(slug, path)
    memory.store_analysis(
        slug,
        path,
        old_content,
        {
            "summary": "STALE SUMMARY: Mara keeps the key forever.",
            "facts": [],
        },
    )
    storage.save_text(
        slug,
        path,
        "# Chapter 1\n\nMara destroys the key and walks into the dawn.\n",
    )
    profile = submissions.default_submission_profile(slug).model_copy(
        update={"author_name": "A. Writer", "genre": "Adult Fantasy"}
    )

    context, documents, used_summaries = submissions._submission_context(slug, profile)

    assert documents >= 1
    assert used_summaries is False
    assert "STALE SUMMARY" not in context
    assert "destroys the key" in context


@pytest.mark.asyncio
async def test_ai_submission_draft_uses_story_context_without_requiring_full_manuscript_in_one_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = use_temp_data(tmp_path)
    target = destination(synopsis_required=False)
    profile = profile_for(slug, target)
    captured: dict = {}

    async def fake_generate(config, messages, temperature=0.9, top_p=0.95, json_mode=False):
        captured["messages"] = messages
        return "Dear Agent,\n\nA grounded query draft."

    monkeypatch.setattr(submissions, "generate", fake_generate)
    text, documents, used_summaries = await submissions.draft_submission_material(
        slug,
        kind="query",
        provider=ProviderConfig(model="test-model"),
        profile=profile,
        destination_id=target.id,
    )

    assert text.startswith("Dear Agent")
    assert documents >= 1
    assert used_summaries is False
    assert "STORY CONTEXT" in captured["messages"][1]["content"]
    assert "Never fabricate" in captured["messages"][0]["content"]
