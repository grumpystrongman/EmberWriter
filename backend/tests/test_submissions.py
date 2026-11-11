from __future__ import annotations

import json
import zipfile
from io import BytesIO
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


def test_authorship_review_tracks_rendered_packet_and_preserves_privacy(tmp_path: Path) -> None:
    from app.provenance_store import record_assistance_event

    slug = use_temp_data(tmp_path)
    target = destination(sample_kind="none")
    profile = profile_for(slug, target)
    retained = "The lantern only burns when a forgotten passenger speaks."
    excluded = "Mara crossed the silent station. She carried the key her brother died to protect."

    def record(mode: str, output: str, original: str | None = None) -> None:
        record_assistance_event(
            slug, mode=mode, active_file="manuscript/chapter-001.md",
            prompt="fixture", selected_text=original, output_text=output,
            context_files=[], refined=False, provider="ollama", model="fixture",
        )

    record("write", excluded)
    record("editorial_feedback", retained)
    record("editorial_wording", excluded, original=excluded)
    record("submission_wording", retained)

    def build(query_letter: str):
        return submissions.build_submission_package(
            slug, profile=profile.model_copy(update={"query_letter": query_letter}),
            destination_id=target.id,
        )[0]

    first = build(retained + " The author added this sentence.")
    review = first.authorship_review
    assert review["matched_events"] == 1
    assert review["recorded_assistance"]["editorial_feedback"] == 1
    assert {item["file"] for item in review["excerpts"]} == {
        "query-letter.txt", "query-letter.docx", "submission-body.txt",
    }
    assert all(item["mode"] == "submission_wording" for item in review["excerpts"])
    root = storage.project_root(slug)
    private_report = root / first.authorship_review_path
    assert json.loads(private_report.read_text(encoding="utf-8")) == review
    zip_path = next(item.relative_path for item in first.artifacts if item.format == "zip")
    with zipfile.ZipFile(root / zip_path) as archive:
        assert private_report.name not in archive.namelist()
        manifest = json.loads(archive.read("submission-manifest.json"))
        assert "authorship_review" not in manifest
        assert all(file in manifest["files"] for file in (
            {key: row[key] for key in ("path", "bytes", "sha256")} for row in review["files"]
        ))

    rewritten = build("A broken signal light draws Mara out to the empty platform.")
    assert rewritten.authorship_review["matched_events"] == 0
    assert rewritten.authorship_review["recorded_assistance"]["submission_wording"] == 1


def test_one_manuscript_produces_three_recipient_specific_packets(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    root = storage.project_root(slug)
    for number in range(2, 5):
        storage.save_text(
            slug, f"manuscript/chapter-{number:03d}.md",
            f"# Chapter {number}\n\nDistinct chapter marker number {number}.\n",
        )
    targets = [
        destination(
            name="Susan Schulman Literary Agency", sample_count=10, accepted_formats=[],
            guidelines_url="https://www.schulmanagency.com/submissions",
            guidelines_text="Query and brief synopsis in the email body.\nPaste the first ten pages.\nAI-created projects are ineligible.",
        ),
        destination(
            name="Fenn & Fable", sample_kind="chapters", sample_count=3, attachment_mode="mixed",
            accepted_formats=["docx"], combine_synopsis=True,
            guidelines_url="https://fennandfable.com/pages/submit",
            guidelines_text="Put a short query in the email.\nAttach a one-page synopsis and first three chapters in a single document.",
        ),
        destination(
            name="Ninth Letter Literary Awards", kind="contest", sample_kind="full", sample_count=0,
            attachment_mode="attachments", accepted_formats=["pdf"], blind_review=True,
            query_required=False, synopsis_required=False,
            guidelines_url="https://ninthletter.com/contestguidelines/",
            guidelines_text="Submit an anonymous manuscript.\nAI-generated writing is ineligible.",
        ),
    ]
    for index, target in enumerate(targets):
        profile = profile_for(slug, target)
        assert not submissions.validate_submission(slug, profile, target.id).valid
        reviewed = target.model_copy(update={"guidelines_reviewed": True})
        profile = profile.model_copy(update={"destinations": [reviewed]})
        result, _ = submissions.build_submission_package(slug, profile=profile, destination_id=target.id)
        zip_path = next(artifact.relative_path for artifact in result.artifacts if artifact.format == "zip")
        with zipfile.ZipFile(root / zip_path) as packet:
            assert "private-authorship-review.json" not in packet.namelist()
            if index == 0:
                assert result.authorship_review["ai_policy_lines"]
                assert "SYNOPSIS" in packet.read("submission-body.txt").decode()
                assert not any(name.endswith((".pdf", ".docx")) for name in packet.namelist())
            elif index == 1:
                manuscript = Document(BytesIO(packet.read("manuscript-sample.docx")))
                content = "\n".join(paragraph.text for paragraph in manuscript.paragraphs)
                assert profile.synopsis in content
                assert "Distinct chapter marker number 3" in content
                assert "Distinct chapter marker number 4" not in content
                assert "synopsis.docx" not in packet.namelist()
            else:
                assert packet.namelist() == ["manuscript-sample.pdf"]
                reader = PdfReader(BytesIO(packet.read("manuscript-sample.pdf")))
                assert not reader.metadata.author
                assert all(profile.author_name not in page.extract_text() for page in reader.pages)
