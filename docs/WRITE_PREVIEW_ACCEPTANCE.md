# EmberWriter Write & Preview Acceptance

This milestone adds professional authoring and preview workflows around the existing manuscript editor.

## Write workspace

- Multiple open-document tabs persist per project.
- A second editable split pane can open another project file without replacing the primary editor.
- Project-wide search returns source paths and excerpts.
- Project-wide replace previews impact first and creates a whole-project checkpoint before applying.
- Bookmarks are author-owned project data and can reopen the linked source file.
- Existing TipTap editing, autosave, revisions, live diagnostics, comments, sprints, and editorial review remain intact.

## Voice Fingerprint

- Quick Voice Lab remains available for a selection/current chapter.
- Manuscript-wide Voice Fingerprint samples across the book rather than only the opening.
- The generated profile saves to `style/voice-profile.json`, so existing Voice Lock and Craft Pass consume it immediately.
- Voice Fingerprint is author-editable through the existing craft profile/voice workflow and does not replace manuscript canon.

## Talk / Idea Capture

- The capture overlay preserves the raw idea text before routing.
- Authors can type or use operating-system dictation in the capture field.
- Ideas can route to the inbox, Beat Sheet, World, Character, Scene, or project notes without silently changing manuscript prose.
- The Idea Inbox is stored as ordinary project data and survives restart/checkpoint workflows.

## Local model setup

- `install.ps1` installs dependencies, installs Ollama when possible, and can pull the recommended local fiction model.
- The setup records the preferred local model under `.ember/local-models.json`.
- EmberWriter does not add a sanitizing layer to consensual adult-fiction requests; actual output remains constrained by the selected local model's capabilities.

## Publishing Preview Studio

- Preview content comes from Binder compile order, not a fake sample.
- Phone, tablet, Kindle-style, and print-trim views render the compiled manuscript.
- Amazon KDP readiness uses the same distribution validation used by Release & Distribution.
- A standalone browser-reader ZIP can be generated for private review.
- The preview ZIP clearly states that remote confidential sharing requires authenticated hosting; the static package itself is not claimed as an access-control boundary.
- EPUB, DOCX, PDF, cover, release metadata, and retailer handoff workflows remain separate production artifacts.

## Verification expectations

CI must pass backend tests, Ruff, and the production frontend build on the exact merge head before this milestone is considered merge-ready.
