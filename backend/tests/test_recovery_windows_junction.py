"""Windows NTFS reparse-point escape must not cause private external files to be backed up."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from app import recovery_vault as recovery
from app import storage


@pytest.mark.skipif(os.name != "nt", reason="NTFS junction coverage only applies on Windows")
def test_windows_junction_outside_library_is_rejected_without_reading_private_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    data_root = tmp_path / "Author QA Library"
    monkeypatch.setattr(storage, "PROJECTS_ROOT", data_root / "projects")
    project = storage.create_project("Synthetic Junction Defense")
    secret = tmp_path / "Other unrelated private files"
    secret.mkdir()
    protected = secret / "secret-not-from-app.md"
    protected.write_text("THIS_CONTENT_MUST_NEVER_ENTER_BACKUP", encoding="utf-8")
    junction = storage.project_root(project["slug"]) / "world" / "outside"
    creation = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(junction), str(secret)],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if creation.returncode != 0:
        pytest.skip("Windows environment does not permit NTFS junction creation")
    try:
        assert junction.is_dir()
        with pytest.raises(ValueError, match="external link|reparse"):
            recovery.create_backup("junction escape QA")
        assert protected.read_text(encoding="utf-8") == (
            "THIS_CONTENT_MUST_NEVER_ENTER_BACKUP"
        )
        assert not recovery.list_generations()
    finally:
        # rmdir removes the junction itself without traversing or deleting its target.
        junction.rmdir()
    completed = recovery.create_backup("after junction cleanup")
    assert recovery.verify(completed["id"])["healthy"]
