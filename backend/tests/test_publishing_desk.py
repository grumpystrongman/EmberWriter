"""Part 4 publishing-desk tests: source lineage, privacy and explicit sign-off."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import publishing_desk, storage
from app.main import app


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    slug = storage.create_project("Synthetic Lighthouse Release")["slug"]
    other = storage.create_project("Private Neighboring Book")["slug"]
    storage.save_text(slug, "manuscript/chapter-001.md",
                      "# Lighthouse\n\nMira opened the glass gate. A storm appeared behind the harbor.\n")
    storage.save_text(other, "manuscript/chapter-001.md", "PRIVATE_NEIGHBOR_PROJECT")
    return slug, other


def test_dashboard_uses_real_source_and_reports_missing_assets(sample):
    slug, _ = sample
    state = publishing_desk.report(slug)
    assert state["project_name"] == "Synthetic Lighthouse Release"
    assert len(state["source_fingerprint"]) == 64
    assert state["chapter_count"] >= 1
    assert state["editorial"]["warnings"] >= 0
    assert not state["files"]
    assert state["reviewed_current"] is False
    assert [stage["id"] for stage in state["stages"]] == [
        "readiness", "interior", "cover", "audio", "distribution", "history"
    ]
    assert "No manuscript is uploaded" in state["privacy"]


def test_private_review_receipt_and_stale_after_manuscript_change(sample):
    slug, other = sample
    state = publishing_desk.report(slug)
    with pytest.raises(ValueError, match="acknowledgment"):
        publishing_desk.signoff(slug, state["source_fingerprint"], "Reviewed a complete book.", False)
    with pytest.raises(ValueError, match="review note"):
        publishing_desk.signoff(slug, state["source_fingerprint"], "short", True)
    accepted = publishing_desk.signoff(
        slug, state["source_fingerprint"],
        "I reviewed the ordered manuscript and identified outstanding retailer warnings.", True,
    )
    assert accepted["local_only"] and accepted["type"] == "author_review_receipt"
    assert not accepted["distribution_valid"]
    current = publishing_desk.report(slug)
    assert current["reviewed_current"] is True
    assert current["receipts"][0]["current"]
    storage.save_text(
        slug, "manuscript/chapter-001.md",
        "# Lighthouse\n\nMira opened another glass gate. The sky turned copper.\n",
    )
    changed = publishing_desk.report(slug)
    assert changed["source_fingerprint"] != state["source_fingerprint"]
    assert changed["reviewed_current"] is False
    assert changed["receipts"][0]["current"] is False
    with pytest.raises(ValueError, match="changed since review"):
        publishing_desk.signoff(
            slug, state["source_fingerprint"], "I reviewed the originally selected manuscript.", True,
        )
    assert not (storage.project_root(other) / ".ember" / "publishing-desk-receipts.json").exists()
    assert json.loads(
        (storage.project_root(slug) / ".ember" / "publishing-desk-receipts.json").read_text()
    )[0]["fingerprint"] == state["source_fingerprint"]


def test_metadata_change_invalidates_review(sample):
    slug, _ = sample
    state = publishing_desk.report(slug)
    from app.distribution import load_release_profile, save_release_profile

    profile = load_release_profile(slug)
    profile.author = "Author One"
    save_release_profile(slug, profile)
    refreshed = publishing_desk.report(slug)
    assert refreshed["source_fingerprint"] != state["source_fingerprint"]


def test_api_report_receipt_and_project_isolation(sample):
    slug, other = sample
    with TestClient(app) as client:
        base = f"/api/projects/{slug}/publishing-desk"
        initial = client.get(base)
        assert initial.status_code == 200, initial.text
        assert "PRIVATE_NEIGHBOR_PROJECT" not in initial.text
        assert client.get("/api/projects/nonexistent/publishing-desk").status_code == 404
        rejected = client.post(base + "/signoff", json={
            "fingerprint": initial.json()["source_fingerprint"],
            "note": "I reviewed the manuscript before exporting anything.",
            "acknowledged": False,
        })
        assert rejected.status_code == 400
        accepted = client.post(base + "/signoff", json={
            "fingerprint": initial.json()["source_fingerprint"],
            "note": "I reviewed the manuscript and its remaining warnings.",
            "acknowledged": True,
        })
        assert accepted.status_code == 201, accepted.text
        assert client.get(base).json()["reviewed_current"] is True
        assert not (storage.project_root(other) / ".ember" / "publishing-desk-receipts.json").exists()


def test_receipt_archive_limit_and_corrupt_file(sample):
    slug, _ = sample
    path: Path = publishing_desk._path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{}] * 101), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid publishing receipt archive"):
        publishing_desk.report(slug)

def test_real_epub_docx_pdf_exports_change_release_fingerprint(sample):
    import zipfile

    from app.publishing import export_project

    slug, _ = sample
    before = publishing_desk.report(slug)
    outcome = export_project(slug, formats=["epub", "docx", "pdf"],
                             title="Synthetic Lighthouse", author="Test Author",
                             include_toc=True, trim_width=6, trim_height=9)
    assert len(outcome["artifacts"]) == 3
    for artifact in outcome["artifacts"]:
        file_path = storage.project_root(slug) / artifact["relative_path"]
        assert file_path.is_file() and file_path.stat().st_size > 100
        if artifact["format"] == "epub":
            with zipfile.ZipFile(file_path) as archive:
                assert archive.read("mimetype") == b"application/epub+zip"
        elif artifact["format"] == "docx":
            with zipfile.ZipFile(file_path) as archive:
                assert "word/document.xml" in archive.namelist()
        elif artifact["format"] == "pdf":
            assert file_path.read_bytes().startswith(b"%PDF-")
    after = publishing_desk.report(slug)
    assert all(after["formats"].values())
    assert before["source_fingerprint"] != after["source_fingerprint"]
    assert len(after["files"]) >= 3
    decision = publishing_desk.signoff(slug, after["source_fingerprint"],
             "Inspected compiled EPUB, PDF and DOCX files and noted remaining release issues.", True)
    assert decision["local_only"]
    export_project(slug, formats=["epub"], title="Recompiled Edition", author="Test Author")
    assert publishing_desk.report(slug)["reviewed_current"] is False
