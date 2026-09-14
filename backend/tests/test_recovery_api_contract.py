from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_recovery_upload_and_historical_forensics_are_exposed() -> None:
    main = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    recovery = (REPO_ROOT / "backend" / "app" / "project_recovery.py").read_text(encoding="utf-8")
    importer = (REPO_ROOT / "backend" / "app" / "importer.py").read_text(encoding="utf-8")

    assert '@app.post("/api/projects/restore-upload")' in main
    assert "webkitRelativePath" not in main
    assert "_historical_windows_launch_roots" in recovery
    assert "ConsoleHost_history.txt" in recovery
    assert 'drive / "$Recycle.Bin"' in recovery
    assert "document_revisions" in recovery
    assert "project_checkpoint_files" in recovery
    assert '".ember" / "snapshots"' in recovery
    assert "restore_uploaded_project" in importer
