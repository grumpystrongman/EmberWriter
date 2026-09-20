from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def source(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_split_editor_has_visible_close_button_and_escape_shortcut() -> None:
    pane = source("SplitEditorPane.tsx")
    tabs = source("WriteTabsBar.tsx")
    workspace = source("WriteWorkspacePro.tsx")

    assert "Close split ×" in pane
    assert 'aria-label="Close split editor"' in pane
    assert "event.key !== 'Escape'" in pane
    assert "splitOpen: boolean" in tabs
    assert "× Close split" in tabs
    assert "aria-pressed={splitOpen}" in tabs
    assert "splitOpen={split}" in workspace
