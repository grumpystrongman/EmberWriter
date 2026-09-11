# EmberWriter v0.12 Writing Environment Acceptance Gate

This checklist is the release gate for the approved full writing-environment redesign. A capability does not pass because a control is visible; it must persist real project data and survive reload.

## Workspace shell

- Open an existing manuscript and verify the new Write / Plan / Characters / World / Analyze / Publish / Submit navigation is present.
- Verify Write keeps the manuscript editor visually dominant.
- Toggle Binder visibility and verify the editor expands without losing the active document.
- Toggle Ember visibility and verify the editor expands without losing generation state.
- Enter Focus mode and verify Binder, assistant chrome and editor header collapse while the rich editor remains editable.
- Reload and verify the selected workspace and Focus preference persist.
- Use Ctrl/Cmd+1–7 to change workspaces and Ctrl/Cmd+Shift+F to toggle Focus.
- Confirm every workspace destination opens or navigates to a real existing tool; no dead navigation items are allowed.

## Project-scoped visual Corkboard

Create two real projects, Book A and Book B.

For Book A:

- Open Plan -> Corkboard -> Visual Board.
- Add at least two sticky notes and enter meaningful planning text.
- Move the notes to distinct coordinates and reload the app; positions and text must persist.
- Pin at least two Binder scenes. Double-click each pinned scene and verify the correct manuscript document opens.
- Upload at least one image and one non-image reference file.
- Verify the image renders from the project-local asset endpoint and the attachment opens from the same project.
- Add an external reference link and verify it remains after reload.
- Remove an uploaded board item and confirm its board reference disappears without destructively deleting the underlying project asset.

Switch to Book B:

- Book A sticky notes, pinned scenes, links and uploads must not appear.
- Book B starts with its own independent visual board.
- Attempting to request Book A's board asset through Book B's project slug must fail.

Switch back to Book A:

- All remaining Book A board items must reappear at their saved positions.

## Project history integration

- Arrange Book A's board and create a whole-project checkpoint.
- Remove a board image/file item and change at least one sticky note.
- Restore the checkpoint.
- Verify `planning/corkboard.json` returns to the captured state.
- Verify the preserved uploaded asset is again reachable through the restored board item.
- Undo the restore using the automatic pre-restore safety checkpoint and verify the later board state returns.

## Regression gate

- Existing rich editing, import, Binder, Outliner, version history, Story Memory, Story Intelligence, Scene Architect, Craft/Voice, Chemistry/Aftermath, Editorial Studio, AI Readers, Cover Studio, publishing, distribution and traditional submission workflows must remain functional.
- Backend test suite must pass.
- Ruff must pass with no ignored new failures.
- TypeScript/Vite production build must pass.
- The exact final PR head must be the head that passed CI.
