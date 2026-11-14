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

def test_scene_boards_survive_private_backup_with_remapped_cast(portable_fixture):
    from app import series_scene_studio as studio
    series_id, _, _ = portable_fixture
    char = canon.add_entity(series_id, "Eira", "character")
    place = canon.add_entity(series_id, "Frozen Keep", "place")
    payload = {
        "title": "The confession", "book": 1, "sequence": 4, "objective": "Tell the truth",
        "conflict": "An oath prevents disclosure", "opening": "Guarded trust",
        "aftermath": "They choose to separate", "voice_notes": "Whispered dialogue",
        "pov_id": char["id"], "location_id": place["id"],
        "participants": [char["id"]],
        "beats": [{"id": "a1", "kind": "reversal", "title": "The confession",
                   "detail": "A secret changes their future", "pressure": 83}],
    }
    original = studio.create_board(series_id, payload)
    archive = portable.backup(series_id)
    try:
        restored = portable.restore(archive.read_bytes(), True)
    finally:
        archive.unlink(missing_ok=True)
    boards = studio.list_boards(restored["id"])
    assert len(boards) == 1
    restored_board = boards[0]
    assert restored_board["id"] != original["id"]
    assert restored_board["version"] == 1
    assert restored_board["beats"] == payload["beats"]
    assert restored_board["aftermath"] == payload["aftermath"]
    entities = {entity["name"]: entity["id"] for entity in canon.list_entities(restored["id"])}
    assert restored_board["pov_id"] == entities["Eira"]
    assert restored_board["location_id"] == entities["Frozen Keep"]
    assert restored_board["participants"] == [entities["Eira"]]
    assert studio.list_boards(series_id)[0]["id"] == original["id"]


def test_verified_epub_and_event_review_survive_portable_restore(tmp_path, monkeypatch):
    from app import series_epub_index as indexes
    from app import series_event_leads as leads
    from app import series_event_reviews as reviews
    from app import series_vault as vault

    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("The Evidence Archive")["id"]
    content = "Before dawn, Ada put away the moonstone. After dawn, Ada recalled the midnight ceremony."
    detail = vault.import_volume(
        sid, "evidence.md", content.encode(), 1, title="First book",
        kind="novel", edition_status="reference", rights_confirmed=True,
    )
    source = detail["volumes"][0]["sources"][0]["id"]
    canon.add_entity(sid, "Ada", "character")
    lead = leads.scan(sid, book=1)["leads"][0]
    staged = reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])
    reviews.review(sid, staged["id"], decision="approved",
                   title="Ada stores the moonstone", event_kind="observed_event",
                   timeline_class="book_sequence", note="Verified first-hand.")
    # Use the same schema as a checked original EPUB but with a synthetic
    # preverified index; portability only transports validated metadata.
    with vault._connect() as con:
        indexes._table(con)
        con.execute(
            """INSERT INTO series_epub_structure_indexes
            (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
            VALUES (?,?,?,?,?,?)""",
            (source, sid, vault.source_text(sid, source)[0]["sha256"], "a" * 64,
             json.dumps([{"index": 0, "title": "Opening", "start": 0,
                          "end": len(content), "confidence": "exact_epub_spine"}]), vault.now()),
        )

    archive = portable.backup(sid)
    try:
        restored = portable.restore(archive.read_bytes(), True)
        result_id = restored["id"]
        new_source = restored["volumes"][0]["sources"][0]["id"]
        assert new_source != source
        assert indexes.read(result_id, new_source)["sections"][0]["title"] == "Opening"
        restored_reviews = reviews.list_events(result_id, status="approved")["events"]
        assert len(restored_reviews) == 1
        assert restored_reviews[0]["is_author_approved"]
        assert restored_reviews[0]["quote"] == lead["quote"]
        assert restored_reviews[0]["source_id"] == new_source
        assert reviews.list_events(sid, status="approved")["total_visible"] == 1
    finally:
        archive.unlink(missing_ok=True)


def test_tampered_event_review_rejected_before_restore_creates_series(tmp_path, monkeypatch):
    from app import series_event_leads as leads
    from app import series_event_reviews as reviews

    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Tamper-Proof Event Evidence")["id"]
    content = b"Before sunrise, Ada closed the door to the palace."
    detail = vault.import_volume(sid, "before.md", content, 1, title="One",
                                 kind="novel", edition_status="reference",
                                 rights_confirmed=True)
    source = detail["volumes"][0]["sources"][0]["id"]
    canon.add_entity(sid, "Ada", "character")
    lead = leads.scan(sid, book=1)["leads"][0]
    reviews.stage(sid, source, lead["quote_start"], lead["quote_end"])
    archive = portable.backup(sid)
    try:
        with zipfile.ZipFile(archive) as original:
            entries = {name: original.read(name) for name in original.namelist()}
        manifest = json.loads(entries["manifest.json"])
        manifest["author_event_reviews"][0]["quote"] = "Invented event with fake citation"
        entries["manifest.json"] = json.dumps(manifest).encode("utf8")
        changed = io.BytesIO()
        with zipfile.ZipFile(changed, "w") as output:
            for name, data in entries.items():
                output.writestr(name, data)
        with pytest.raises(ValueError, match="Event review quote"):
            portable.restore(changed.getvalue(), True)
        assert len(vault.list_series()) == 1
    finally:
        archive.unlink(missing_ok=True)


def test_old_format_backup_without_new_fields_still_restores(portable_fixture):
    series_id, _, _ = portable_fixture
    archive = portable.backup(series_id)
    try:
        with zipfile.ZipFile(archive) as reader:
            entries = {name: reader.read(name) for name in reader.namelist()}
        manifest = json.loads(entries["manifest.json"])
        manifest.pop("verified_epub_indexes", None)
        manifest.pop("author_event_reviews", None)
        entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
        previous = io.BytesIO()
        with zipfile.ZipFile(previous, "w") as writer:
            for name, content in entries.items():
                writer.writestr(name, content)
        restored = portable.restore(previous.getvalue(), True)
        assert restored["id"] != series_id
        assert restored["title"] == "The Winter Archive"
    finally:
        archive.unlink(missing_ok=True)


def test_bad_epub_index_source_offsets_are_rejected(tmp_path, monkeypatch):
    from app import series_epub_index as indexes
    from app import series_vault as vault

    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Index Integrity")["id"]
    detail = vault.import_volume(
        sid, "short.md", b"An immutable little text.", 1,
        title="One", kind="novel", edition_status="reference", rights_confirmed=True,
    )
    source = detail["volumes"][0]["sources"][0]["id"]
    with vault._connect() as con:
        indexes._table(con)
        con.execute(
            """INSERT INTO series_epub_structure_indexes
            (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
            VALUES (?,?,?,?,?,?)""",
            (source, sid, vault.source_text(sid, source)[0]["sha256"], "b" * 64,
             json.dumps([{"start": 0, "end": 4, "title": "Valid"}]), vault.now()),
        )
    archive = portable.backup(sid)
    try:
        with zipfile.ZipFile(archive) as reader:
            entries = {name: reader.read(name) for name in reader.namelist()}
        manifest = json.loads(entries["manifest.json"])
        manifest["verified_epub_indexes"][0]["sections_json"] = json.dumps(
            [{"start": 0, "end": 99999, "title": "Forged chapter"}])
        entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
        changed = io.BytesIO()
        with zipfile.ZipFile(changed, "w") as writer:
            for name, data in entries.items():
                writer.writestr(name, data)
        with pytest.raises(ValueError, match="EPUB index coordinates"):
            portable.restore(changed.getvalue(), True)
        assert len(vault.list_series()) == 1
    finally:
        archive.unlink(missing_ok=True)
