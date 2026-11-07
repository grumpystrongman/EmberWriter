"""Portable multi-book Series Vault backup and verified restore contracts."""
from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_portability as portable
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def portable_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    project = storage.create_project("Protected Legacy Manuscript")
    original = storage.read_text(project["slug"], "manuscript/chapter-001.md")
    series = vault.create_series("The Winter Archive")
    first = vault.import_volume(
        series["id"], "book-one.md",
        b"The Ivory Ring rested beneath the ancient oak.", 1,
        title="The Frozen Gate", kind="novel",
        edition_status="published", rights_confirmed=True)
    vault.attach_project(
        series["id"], project["slug"], 2, title="The Spring Return",
        kind="novel", edition_status="draft", rights_confirmed=True)
    item = canon.add_entity(series["id"], "Ivory Ring", "artifact", aliases=["the ring"])
    src = first["volumes"][0]["sources"][0]
    phrase = "The Ivory Ring rested beneath the ancient oak."
    proposal = canon.propose_fact(
        series["id"], item["id"], "located_in",
        object_text="beneath the ancient oak",
        start_book=1, source_id=src["id"],
        quote_start=0, quote_end=len(phrase), quote=phrase,
    )
    canon.review_fact(series["id"], proposal["id"], "approved")
    return series["id"], project["slug"], original


def test_backup_restores_new_independent_series_and_all_source_provenance(portable_fixture):
    series_id, slug, original = portable_fixture
    archive = portable.backup(series_id)
    try:
        result = portable.restore(archive.read_bytes(), True)
    finally:
        archive.unlink(missing_ok=True)
    assert result["id"] != series_id
    assert result["title"] == "The Winter Archive"
    assert len(result["volumes"]) == 2
    assert all(volume["project_slug"] is None for volume in result["volumes"])
    assert storage.read_text(slug, "manuscript/chapter-001.md") == original
    entities = canon.list_entities(result["id"])
    assert len(entities) == 1
    assert entities[0]["aliases"] == ["the ring"]
    as_of = canon.ask_temporal(result["id"], "Where is the Ivory Ring?", 1)
    assert "ancient oak" in as_of["answer"]
    assert as_of["sources"][0]["quote"] == "The Ivory Ring rested beneath the ancient oak."
    assert not canon.at_book(result["id"], 2)["conflicts"]
    assert len(vault.list_series()) == 2


def test_tampered_backup_is_rejected_before_new_series_is_created(portable_fixture):
    series_id, _, _ = portable_fixture
    archive = portable.backup(series_id)
    try:
        with zipfile.ZipFile(archive) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        name = next(key for key in entries if key.startswith("sources/"))
        entries[name] = b"FAKE CONTENT THAT DOES NOT MATCH ITS SHA"
        corrupted = io.BytesIO()
        with zipfile.ZipFile(corrupted, "w") as writer:
            for path, data in entries.items():
                writer.writestr(path, data)
        with pytest.raises(ValueError, match="checksum"):
            portable.restore(corrupted.getvalue(), True)
        assert len(vault.list_series()) == 1
    finally:
        archive.unlink(missing_ok=True)


def test_zip_slip_and_unauthorized_restore_are_blocked(portable_fixture):
    series_id, _, _ = portable_fixture
    archive = portable.backup(series_id)
    try:
        with pytest.raises(ValueError, match="Confirm"):
            portable.restore(archive.read_bytes(), False)
        malicious = io.BytesIO()
        with zipfile.ZipFile(malicious, "w") as writer:
            writer.writestr("../outside.txt", "should never be extracted")
            writer.writestr("manifest.json", json.dumps({"version": 1}))
        with pytest.raises(ValueError, match="unexpected"):
            portable.restore(malicious.getvalue(), True)
        assert len(vault.list_series()) == 1
    finally:
        archive.unlink(missing_ok=True)


def test_series_backup_and_restore_http_routes(portable_fixture):
    series_id, _, _ = portable_fixture
    with TestClient(app) as client:
        download = client.get(f"/api/series/{series_id}/backup")
        assert download.status_code == 200
        assert download.content[:2] == b"PK"
        denied = client.post("/api/series/restore",
                             data={"rights_confirmed": "false"},
                             files={"file": ("archive.zip", download.content, "application/zip")})
        assert denied.status_code == 400
        restored = client.post("/api/series/restore",
                               data={"rights_confirmed": "true"},
                               files={"file": ("archive.zip", download.content, "application/zip")})
        assert restored.status_code == 201, restored.text
        assert restored.json()["id"] != series_id


def test_series_removal_requires_exact_title_and_never_deletes_linked_book(portable_fixture):
    series_id, slug, original = portable_fixture
    before = vault.series_detail(series_id)
    with pytest.raises(ValueError, match="exact series title"):
        vault.delete_series(series_id, "incorrect")
    assert len(vault.list_series()) == 1
    result = vault.delete_series(series_id, before["title"])
    assert result["deleted"] is True
    assert result["linked_projects_deleted"] is False
    assert storage.read_text(slug, "manuscript/chapter-001.md") == original
    assert not vault.list_series()
    for volume in before["volumes"]:
        with pytest.raises(FileNotFoundError):
            vault.source_text(series_id, volume["sources"][0]["id"])
