"""Recovery Vault contract: recover complete author data, not only series prose."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import recovery_vault as recovery
from app import storage
from app.main import app


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "author-library"
    monkeypatch.setattr(storage, "PROJECTS_ROOT", data / "projects")
    data.mkdir()
    # Test backup on a completely isolated working data directory.
    assert recovery._data_root() == data.resolve()
    return data


def _make_project() -> dict:
    return storage.create_project("The Hidden Sea")


def test_complete_backup_versioning_and_safe_verified_recovery(library: Path):
    project = _make_project()
    path = storage.project_root(project["slug"]) / "manuscript" / "chapter-001.md"
    original = path.read_bytes()
    assets = library / "visual-assets" / "inspiration.webp"
    assets.parent.mkdir(parents=True)
    assets.write_bytes(b"synthetic-image-references\x00\x01")
    audio = library / "audio" / "narrator.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"RIFF" + b"synthetic-audio" * 64)
    cache = library / "custom-metadata.json"
    cache.write_text('{"key":"fiction"}', encoding="utf-8")
    con = sqlite3.connect(library / "series.sqlite3")
    con.execute("CREATE TABLE facts (name TEXT)")
    con.execute("INSERT INTO facts VALUES ('moon key')")
    con.commit()
    con.close()

    first = recovery.create_backup("before edits")
    assert first["verified"]
    assert recovery.verify(first["id"])["healthy"]
    assert recovery.preview_restore(first["id"])["includes_media"]
    assert recovery.preview_restore(first["id"])["projects"] == [project["slug"]]

    storage.save_text(project["slug"], "manuscript/chapter-001.md", "# New chapter\n\nRewritten.")
    assets.write_bytes(b"new-image-binary")
    second = recovery.create_backup("after edits")
    assert first["id"] != second["id"]
    assert len(recovery.list_generations()) == 2

    destination = library.parent / "restored-first"
    restored = recovery.restore(first["id"], destination=str(destination))
    assert restored["restored"] and not restored["current_library_changed"]
    assert (destination / "projects" / project["slug"] / "manuscript" / "chapter-001.md").read_bytes() == original
    assert (destination / "visual-assets" / "inspiration.webp").read_bytes() == b"synthetic-image-references\x00\x01"
    assert (destination / "audio" / "narrator.wav").read_bytes() == audio.read_bytes()
    connection = sqlite3.connect(destination / "series.sqlite3")
    assert connection.execute("SELECT name FROM facts").fetchone()[0] == "moon key"
    connection.close()
    assert "Rewritten" in path.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        recovery.restore(first["id"], destination=str(destination))
    assert recovery.verify(second["id"])["healthy"]


def test_corrupt_object_refuses_restore_and_preserves_existing_live_book(library: Path):
    project = _make_project()
    before = storage.read_text(project["slug"], "manuscript/chapter-001.md")
    generation = recovery.create_backup()
    manifest = recovery._read_manifest(recovery._backup_root(), generation["id"])
    manuscript = next(row for row in manifest["files"]
                      if row["path"].endswith("manuscript/chapter-001.md"))
    obj = recovery._object(recovery._backup_root(), manuscript["sha256"])
    obj.write_bytes(b"corrupted snapshot, not a manuscript")
    assert not recovery.verify(generation["id"])["healthy"]
    with pytest.raises(ValueError, match="damaged"):
        recovery.restore(generation["id"], destination=str(library.parent / "bad-restore"))
    with pytest.raises(ValueError, match="corrupted"):
        recovery.create_backup()
    assert storage.read_text(project["slug"], "manuscript/chapter-001.md") == before


def test_interrupted_backup_never_publishes_incomplete_generation(library: Path,
                                                                 monkeypatch: pytest.MonkeyPatch):
    _make_project()
    original = recovery._store_object
    calls = 0

    def interrupted(root, file):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("simulated power interruption")
        return original(root, file)

    monkeypatch.setattr(recovery, "_store_object", interrupted)
    with pytest.raises(OSError, match="interruption"):
        recovery.create_backup()
    assert recovery.list_generations() == []
    monkeypatch.setattr(recovery, "_store_object", original)
    good = recovery.create_backup()
    assert recovery.verify(good["id"])["healthy"]


def test_destructive_operations_require_backup_before_deletion(library: Path,
                                                              monkeypatch: pytest.MonkeyPatch):
    project = _make_project()
    path = "manuscript/chapter-001.md"
    before = storage.read_text(project["slug"], path)
    def fail_backup(action, protected_paths=None):
        raise OSError("recovery drive unavailable")
    with monkeypatch.context() as guarded:
        guarded.setattr(recovery, "before_destructive_action", fail_backup)
        with pytest.raises(OSError, match="unavailable"):
            storage.delete_text(project["slug"], path)
        with pytest.raises(OSError, match="unavailable"):
            storage.delete_project(project["slug"])
        assert storage.read_text(project["slug"], path) == before
    deleted = storage.delete_text(project["slug"], path)
    assert deleted["deleted"]
    assert recovery.list_generations()


def test_backup_config_must_be_outside_live_work_and_can_disable_schedule(library: Path):
    with pytest.raises(ValueError, match="outside"):
        recovery.configure(str(library / "backups"))
    with pytest.raises(ValueError, match="outside"):
        recovery.configure(str(library))
    separate = library.parent / "separate-recovery-drive-simulation"
    result = recovery.configure(str(separate), automatic=False)
    assert not result["automatic"]
    assert recovery.backup_if_due() is None
    assert recovery.create_backup()["verified"]
    assert (separate / ".ember-recovery-store").exists()
    assert recovery.status()["snapshot_count"] == 1


def test_symlink_escape_and_unsafe_restore_manifest_are_blocked(library: Path):
    project = _make_project()
    outside = library.parent / "outside-sensitive-file.txt"
    outside.write_text("never copy me", encoding="utf-8")
    linked = storage.project_root(project["slug"]) / "manuscript" / "unsafe.txt"
    try:
        linked.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("This Windows account cannot create symlinks")
    with pytest.raises(ValueError, match="external link"):
        recovery.create_backup()
    linked.unlink()
    generation = recovery.create_backup()
    file = recovery._snapshot_path(recovery._backup_root(), generation["id"])
    record = json.loads(file.read_text(encoding="utf-8"))
    record["files"][0]["path"] = "..\\..\\outside-sensitive-file.txt"
    file.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe"):
        recovery.preview_restore(generation["id"])
    assert outside.read_text(encoding="utf-8") == "never copy me"


def test_recovery_http_status_create_preview_verify_restore(library: Path):
    _make_project()
    with TestClient(app) as client:
        status = client.get("/api/recovery/status")
        assert status.status_code == 200
        assert status.json()["automatic"]
        made = client.post("/api/recovery/backup", json={"reason": "test on demand"})
        assert made.status_code == 201, made.text
        identifier = made.json()["id"]
        preview = client.get(f"/api/recovery/generations/{identifier}")
        assert preview.status_code == 200
        assert preview.json()["total_files"] > 0
        health = client.post(f"/api/recovery/generations/{identifier}/verify")
        assert health.status_code == 200
        assert health.json()["healthy"]
        refused = client.post(f"/api/recovery/generations/{identifier}/restore",
                              json={"confirmed": False})
        assert refused.status_code == 400
        restored = client.post(f"/api/recovery/generations/{identifier}/restore",
                               json={"confirmed": True})
        assert restored.status_code == 201
        assert restored.json()["current_library_changed"] is False


def test_mirror_redundancy_and_offline_drive_repair(library: Path):
    project = _make_project()
    primary = library.parent / "primary-recovery"
    external = library.parent / "external-encrypted-drive-simulation"
    recovery.configure(str(primary), automatic=True, mirror_directory=str(external))
    first = recovery.create_backup("important chapter")
    assert first["mirror_healthy"] is True
    assert recovery._snapshot_path(external, first["id"]).exists()
    assert recovery.status()["mirror_latest_present"] is True
    manuscript = storage.read_text(project["slug"], "manuscript/chapter-001.md")
    # Repoint primary to its independent mirror and recover from the mirrored
    # generation after the original primary has been made unavailable.
    recovery.configure(str(external), automatic=False)
    result = recovery.restore(first["id"], destination=str(library.parent / "from-external-mirror"))
    recovered = Path(result["directory"]) / "projects" / project["slug"] / "manuscript" / "chapter-001.md"
    assert recovered.read_text(encoding="utf-8") == manuscript
    assert recovery.verify(first["id"])["healthy"]


def test_predelete_blocks_if_configured_mirror_is_unavailable(library: Path):
    project = _make_project()
    primary = library.parent / "primary-for-mirror-outage"
    external = library.parent / "external-temporarily-offline"
    recovery.configure(str(primary), mirror_directory=str(external))
    mirror_marker = external / ".ember-recovery-store"
    mirror_marker.unlink()
    # Primary may still save the generation, but required redundancy is not
    # considered verified; a destructive operation must fail closed.
    with pytest.raises(ValueError, match="mirror failed"):
        storage.delete_project(project["slug"])
    assert (storage.project_root(project["slug"]) / "project.json").exists()
    assert recovery.list_generations()
    recovery._atomic_bytes(mirror_marker, b"EmberWriter Recovery Vault v1\n")
    sync = recovery.repair_mirror()
    assert sync["configured"] and sync["remaining"] == 0
    assert recovery.status()["mirror_latest_present"]
