from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_import_folder_picker_is_configured_after_panel_mount() -> None:
    main = (REPO_ROOT / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
    helper = (REPO_ROOT / "frontend" / "src" / "folder-picker-directory.ts").read_text(
        encoding="utf-8"
    )

    assert "import './folder-picker-directory'" in main
    assert "MutationObserver" in helper
    assert "input.hidden-file-input" in helper
    assert ":not([accept])" in helper
    assert "input.setAttribute('webkitdirectory', '')" in helper
    assert "input.setAttribute('directory', '')" in helper
