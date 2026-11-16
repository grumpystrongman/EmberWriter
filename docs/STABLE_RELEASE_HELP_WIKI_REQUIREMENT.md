# Stable Release Requirement — EmberWriter Wiki and Guided Ember Help

**Status:** Accepted requirement, not implemented. Build and validate the full guide only against a stable, versioned EmberWriter release.

## Product experience

A complete, beautiful, searchable, offline-first **How-To Wiki** must document every supported author workflow. The floating Ember Companion must use the same release-verified material to guide authors one step at a time, including contextual navigation, optional screen highlighting, observable progress, and explicit permissions for consequential actions.

No new "MS Forms" UI. Present articles with task-focused screenshots, small interactive step cards, a clear progress trail, contextual sidebars, keyboard accessibility and a visible **Guide me with Ember** action. Help must work with no model and no internet.

## Required wiki categories

1. Getting started, installation, upgrades, local files, projects, import, first-book walkthrough.
2. Writing, Binder, corkboard, outliner, scenes, document versions, search and recovery.
3. Planning, Book Studio, generation and local model diagnostics.
4. Characters, relationships, worldbuilding, source-linked Series canon, Story Observatory, Scene Director and chronology.
5. Manuscript Pulse, Arc and Promise Atlas, Dialogue Studio, Revision Workbench, review/rollback, critique, voice and research.
6. Publishing Desk, previews, EPUB/DOCX/PDF, covers, audio, release profiles, submission materials, private receipts, backups.
7. Privacy and local/remote provider permissions, offline behavior, troubleshooting, accessibility and keyboard shortcuts.
8. Advanced multi-book workflow examples and author-oriented tutorials.

Each how-to must contain: a stable article ID, supported release version, title and keywords, prerequisites, starting app location, numbered actions, stable control IDs, expected state after each step, screenshots from the actual release (desktop and mobile where appropriate), known issues, troubleshooting, undo/recovery actions, related articles, and a verified acceptance-test reference.

## Ember guided-walkthrough contract

- Build a locally indexed, machine-readable corpus of verified Markdown articles. A read-only Help search/API returns exact article and step identifiers. Answers must cite the specific article and release, not hallucinate feature names.
- The application provides current workspace, selected tool, UI version and capabilities through typed state. The assistant must not guess which screen is shown.
- Help search must operate without enabling project manuscript reading. Project passages require separate explicit consent, preserving Ember Companion's existing per-question privacy boundary.
- Offer one focused step at a time: Next, Back, Retry, Exit, and an accessible visual highlight when the target control is present. When a target is missing, disclose the mismatch and provide manual fallback.
- Progress must be verified by observable UI state or explicitly confirmed by the author; never falsely claim a step is complete.
- Navigational assistance is opt-in. No automatic manuscript edits, canon approvals, uploads, submissions, retail publication or destructive actions. Continue relying on existing confirmation and recovery flows.
- Guide progress can be stored locally without copying manuscript contents. Ensure version mismatch, partial completions and cancellation are handled truthfully.
- The floating helper currently resides in frontend/src/EmberCompanion.tsx and uses a tiny hard-coded guide list. Replace that with the full validated corpus and guided-mode component once the stable UI is frozen.

## Post-stable implementation stages

**H1 — Release inventory:** enumerate all real workflows, controls, formats, error states, routes and permission gates from the exact stable build. Capture actual screenshots, never conceptual mockups.

**H2 — Author documentation:** write complete step-by-step articles and a first-book learning path; add local search, category navigation and links. Write and validate metadata and target selectors.

**H3 — Ember grounded help:** integrate local Help search into the floating assistant, require article citations and surface version-specific instructions even with no local model.

**H4 — Interactive walkthroughs:** step cards, navigation support, targeted highlights, context-aware progress verification, accessible fallback and explicit permission gates.

**H5 — Professional author acceptance:** verify creating/importing books, outlining, writing/reordering, Series canon, scene planning, source citations, editorial review and rollback, preview/EPUB/DOCX/PDF compile, private release signoff, backup and recovery, local model troubleshooting. Validate keyboard-only, screen-reader, high-zoom, reduced-motion, 390px/900px/1440px layouts.

## Stable release exit criteria

- Every documented target must be verified against the shipping UI and marked with release compatibility.
- No invented controls, outcomes, generated evidence, or unauthorized project access.
- Guided examples must pass in a synthetic project, including success, failure, cancellation and permission denial.
- Changes to the UI must trigger documentation review and re-verification.
- Help articles are version controlled and can be revised between releases; the assistant never claims guidance is current without a matching release.

This is a **release acceptance gate**, not a declaration the wiki or guided Ember engine exists yet.
