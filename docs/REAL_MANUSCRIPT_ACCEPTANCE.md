# EmberWriter Real-Manuscript Acceptance Gate

A release is not accepted because unit tests pass or because UI controls render. The final release gate must use a real author-owned work with enough length and complexity to expose import, editing, continuity, memory, version-control, and publishing failures.

## Required evidence

For every capability below, record:

- source manuscript and original checksum/word count where available;
- action performed;
- expected result;
- actual persisted result after reopening the project;
- any generated database/file state;
- any defect found and the commit that fixes it;
- PASS/FAIL.

Do not mark a capability PASS from a mocked response, fixture-only test, disabled model call, placeholder UI, or file-extension check.

## Candidate dogfood corpus

Use one of Jeff Barnes's real fiction works. Preferred corpus when available: **THE NAMES WE BURIED**, because it contains a long novel structure, dual historical/present-day continuity, recurring characters, mysteries/secrets, research-heavy lore, and real submission/publishing material. If the complete manuscript is not available in the test environment, use the largest authentic manuscript artifact available and explicitly record the limitation rather than substituting generated filler.

## 1. Project and persistence

- Create a new Story Project.
- Close/restart the app and confirm project discovery.
- Confirm ordinary source files exist outside SQLite and remain readable.
- Confirm `.ember/story.db` exists and can be rebuilt without replacing the manuscript as source of truth.
- Confirm project/Binder state survives restart.

## 2. Import and ingest

Exercise every supported import type with authentic author material or a lossless conversion of it:

- DOCX
- PDF
- EPUB
- RTF
- Markdown
- TXT
- HTML
- pasted text
- local-directory import

For each format:

- import as whole novel where appropriate;
- import as novel portion;
- import as idea/note;
- import as research;
- verify chapter/prologue/epilogue detection where applicable;
- verify imported Binder placement;
- verify compile inclusion/exclusion rules;
- verify imported text is editable;
- verify baseline revisions exist;
- verify invalid/unsupported imports do not leave orphan projects or files.

## 3. Binder

- Open every root: Draft, Research, Story Bible, Trash.
- Create folders/documents/notes/research/character entries.
- Rename and edit Binder metadata.
- Reorder siblings and nested items.
- Move an item to Trash and restore it.
- Synchronize Binder against project files.
- Confirm stable node IDs remain consistent across Tree, Corkboard, and Outliner.
- Confirm missing source files are surfaced rather than silently recreated.

## 4. Corkboard

- Open Corkboard for a folder containing multiple real scenes/chapters.
- Edit synopsis, POV, location, status, label, target word count, and other exposed card metadata.
- Drag cards to reorder.
- Return to Tree/Outliner and verify identical order/state.
- Restart and verify persisted order/state.

## 5. Outliner

- Open a manuscript-wide subtree.
- Edit each exposed inline metadata field.
- Toggle compile inclusion.
- Edit keywords/timeline fields.
- Sort/reorder only through supported operations and confirm Binder remains authoritative.
- Restart and verify persisted metadata.

## 6. Rich manuscript editor

On real prose, exercise:

- normal paragraphs;
- H1/H2/H3 headings;
- bold;
- italic;
- underline;
- strike;
- highlight;
- bullet lists;
- ordered lists;
- block quotes;
- scene breaks;
- left/center/right alignment;
- undo/redo;
- spellcheck surface;
- selected-text operations;
- autosave;
- explicit Save.

Then close/reopen the document and confirm the formatting that Ember exposes survives Markdown round-trip and remains readable outside the app.

## 7. AI model gateway

With a real configured model endpoint:

- model discovery;
- Ollama path when available;
- OpenAI-compatible path when available;
- Write;
- Continue;
- Rewrite selected prose;
- Brainstorm;
- Critic;
- Continuity;
- Append result;
- Replace selected text;
- verify context-files-used reporting;
- verify failure behavior when model endpoint is unavailable.

No AI feature is accepted from a stubbed response.

## 8. Narrative Memory Engine

Using real chapters:

- Analyze active chapter.
- Build all manuscript memory.
- Verify unchanged content hashes skip redundant analysis.
- Edit a chapter and verify re-analysis replaces stale derived facts.
- Inspect fact source paths, confidence, importance, chapter order, and fact types.
- Verify character knowledge is distinct from objective canon.
- Verify timeline, unresolved-thread, relationship, location, object, and ability facts when present in the corpus.
- Search/filter memory.
- Restart and verify persistence.

## 9. Story Intelligence

- Verify character dossiers merge with extracted state.
- Verify character-specific knowledge.
- Verify relationship edges and source history.
- Open source passages from intelligence views.
- Verify current state changes after edited/re-analyzed manuscript passages.

## 10. Scene Architect

Using the real novel state:

- choose POV;
- choose multiple participants;
- choose/set location;
- set objective/conflict/heat;
- generate a scene plan;
- verify causal beats, emotional arc, relationship movement, reveals, continuity requirements, unresolved threads, intimacy notes when relevant, ending state, and next-scene pressure;
- save the plan;
- reopen the saved plan;
- send it to Writer;
- generate prose from it and verify canon/knowledge boundaries are respected.

## 11. Craft Engine / Voice Lab

- Change heat level.
- Change tension curve.
- Change sensory intensity.
- Change dialogue intensity.
- Change interiority.
- Save project craft rules/avoidances.
- Analyze a substantial real prose sample in Voice Lab.
- Save Voice Lock profile.
- Generate with Voice Lock enabled/disabled and compare behavior.
- Run optional Craft Pass and verify it is a second model call that preserves scene facts while improving prose.
- Restart and verify profiles persist as readable project files.

## 12. Relationship Chemistry / Aftermath

On a real relationship-heavy scene:

- infer chemistry for a pair/group;
- inspect/save profile;
- reopen profile;
- analyze scene aftermath;
- inspect proposed relationship/state changes before applying;
- apply reviewed aftermath;
- verify Story Intelligence/relationship state updates;
- verify source attribution and persistence.

## 13. Document revision history

- Save a known original passage.
- Make a substantial edit.
- Verify both revisions exist in SQLite.
- Create a labeled checkpoint.
- Diff old revision vs current.
- Restore the older revision.
- Verify the restored text is exact.
- Verify the newer disliked revision still exists.
- Undo the restore by restoring the later revision.
- Restart and repeat history inspection.

## 14. Whole-project checkpoints

- Create a named whole-project checkpoint.
- Edit multiple chapters.
- change Binder order and metadata;
- create a new file;
- delete/move another file where supported;
- compare checkpoint to current and verify modified/added/deleted paths;
- restore checkpoint;
- require zero-diff comparison to the restored checkpoint;
- verify post-checkpoint files disappear as expected;
- verify Binder and manuscript state are exact;
- verify automatic pre-restore safety checkpoint exists;
- restore the safety checkpoint and prove the rollback itself is reversible.

## 15. Compile order and exclusion

- Reorder real chapters/scenes in Binder.
- Disable at least one document from Compile.
- Compile and verify order matches Binder exactly.
- Verify excluded document content is absent from every output format.
- Re-enable and recompile to confirm it returns.

## 16. Publishing/export

Build all currently supported outputs from the same real project:

- DOCX
- EPUB
- PDF

For DOCX:

- reopen with a DOCX parser;
- verify title/author metadata where applicable;
- verify chapter order and content;
- verify paragraphs/headings are structurally usable for editorial/submission work.

For EPUB:

- reopen as EPUB;
- verify package is valid/readable;
- verify chapter XHTML exists in correct order;
- verify navigation/TOC when enabled;
- verify real content is present and excluded content absent.

For PDF:

- reopen with a PDF parser;
- verify `%PDF` signature;
- verify selected trim dimensions;
- verify title/author text;
- verify chapter order/content;
- inspect representative rendered pages for clipping, missing text, broken pagination, or corrupt characters.

Record that KDP and other distributors can change their current upload requirements; compatibility claims must be checked against current publisher documentation at acceptance time.

## 17. Recovery and corruption resistance

- Restart services during normal use and verify saved content survives.
- Confirm autosave snapshots exist.
- Restore a filesystem snapshot.
- Verify database-backed revisions still exist.
- Verify a project remains usable if derived narrative memory is rebuilt.
- Verify invalid path traversal and unsupported file types are rejected.
- Verify failed imports do not damage an existing project.

## 18. Final author review

The release is not accepted until the author can:

1. open the real imported work;
2. recognize the manuscript structure and prose as intact;
3. edit it comfortably;
4. use the AI/craft/story-intelligence workflows without leaving the project;
5. intentionally make a bad change and recover from it;
6. intentionally make a bad multi-file/project change and recover from it;
7. build DOCX, EPUB, and PDF;
8. open and inspect all three outputs;
9. confirm the outputs represent the intended book and compile order.

Any FAIL in this gate becomes a release-blocking defect unless the capability is explicitly removed from the product UI and documentation.