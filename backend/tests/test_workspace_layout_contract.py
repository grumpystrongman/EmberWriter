from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def source(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8")


def test_write_workspace_has_no_permanent_ai_right_rail() -> None:
    shell = source("WorkspaceShell.tsx")
    css = source("workspace-shell.css")
    main = source("main.tsx")

    assert "assistantCollapsed" not in shell
    assert "Toggle Ember" not in shell
    assert "grid-template-areas: \"library editor\"" in css
    assert ".workspace-shell .assistant" in css
    assert "display: none !important" in css
    assert "AuthorCaptureOverlay" not in main


def test_studio_is_the_single_destination_for_ai_writing_briefs() -> None:
    shell = source("WorkspaceShell.tsx")
    studio = source("AIStudioWorkspace.tsx")

    assert "setWorkspace('studio')" in shell
    assert "injectStudioBrief" in shell
    assert "Scene Writer" in shell
    assert "STUDIO SCENE DELIVERY CONTRACT:" in studio
    assert "Continue this scene" in studio


def test_notes_and_tools_are_top_level_workspaces() -> None:
    shell = source("WorkspaceShell.tsx")
    center = source("CenterWorkspace.tsx")
    types = source("workspace-types.ts")

    assert "label: 'Notes'" in shell
    assert "label: 'Tools'" in shell
    assert "workspace === 'notes'" in center
    assert "workspace === 'tools'" in center
    assert "'notes'" in types and "'tools'" in types


def test_global_sticky_note_saves_to_project_idea_inbox() -> None:
    shell = source("WorkspaceShell.tsx")
    overlay = source("StickyNoteOverlay.tsx")
    notes = source("NotesWorkspace.tsx")
    capture = source("capture-store.ts")

    assert "emberwriter:new-sticky-note" in shell
    assert "emberwriter:new-sticky-note" in overlay
    assert "createCapture(body, 'idea', 'inbox', 'typed')" in overlay
    assert "saveInbox(project, [item, ...latest])" in overlay
    assert "activeDocumentPath()" in overlay
    assert "loadInbox" in notes and "Archive" in notes and "Restore" in notes
    assert "planning/idea-inbox.json" in capture
