# Part 4 — Publishing Command Deck and Private Interior Studio

**Implementation branch:** feature/part-4-publishing-command-deck, stacked on Part 3.
**Status:** Author-review build; not merged or production-stable.
**Date:** November 12, 2026.

## Goal

An author must be able to move from an actual manuscript to a private release package in an elegant, guided, visually engaging publishing workspace, without filling in a long form or uploading any writing. Every consequential action is explicit. This implementation reuses the existing publishing, preview, cover, audio, release validation, submissions, and project-checkpoint tools, rather than reimplementing or compromising their safeguards.

## 1 — Publishing Command Deck

The **Publish** workspace now starts in a guided Publishing Desk with six selectable, interactive milestones:

- **Manuscript check:** Existing preflight warnings, blockers, waivers, and direct access to the full issue/author-waiver workflow.
- **Book interiors:** Existing EPUB, DOCX and PDF files, Binder-based chapter ordering, interior preview access, compile presets.
- **Cover and identity:** Existing cover asset summary, author/title metadata and direct access to Cover Studio. The miniature cover is visibly illustrative, not an exported cover asset.
- **Narration:** Explicitly optional local audiobook preparation and proofing.
- **Release packages:** Saved edition/retailer targets, local release validations, submission and package workflows, and authoritative issue details.
- **Recovery:** Previously generated files, publishing review receipts and existing project checkpoints.

Selecting a milestone reveals a **focused inspector**, not a long metadata form. The chosen chapter can be opened in the existing editor. All milestone links route to the existing workspaces.

A shelf of **actual local export artifacts** shows formats, file size, provenance hash and safe download links. Files from another project are not scanned. Empty shelves have an actionable state.

### Author review receipts

The backend derives a source fingerprint from the **actual ordered manuscript content**, release metadata and current export file hashes. An author may deliberately record a private review note (minimum 12 characters), acknowledge that it is not approval/publication, and confirm again before recording the receipt. No external action follows.

The review history includes dated receipts and displays whether each matches the current manuscript, metadata and exported files. Changing the manuscript, metadata, export selection or asset bytes makes a previous receipt stale. Outstanding warnings and validation errors remain visible and are recorded as such, rather than disappearing or falsely blocking an author's choices.

New read-only API: GET /api/projects/{slug}/publishing-desk.
New explicit private record endpoint: POST /api/projects/{slug}/publishing-desk/signoff.
Receipt persistence: local project/.ember/publishing-desk-receipts.json, with atomic writes and a bounded archive.

## 2 — Interior Atelier

Inside Publish → Book Files, a visually rich, author-operated interior studio now provides:

- **Digital edition** (EPUB), **Editorial manuscript** (DOCX), **Print interior** (PDF), and **Complete set** (all three), each as a selectable illustrated card.
- A live manuscript **reader preview** with Phone, eReader, Tablet and Print presentation modes.
- Chapter-by-chapter navigation based on Binder compilation order, with the content sourced from the project's existing preview API.
- A collapsible inspector for book title, author/pen name, and standard trim sizes.
- Explicit, two-step local compile confirmation and links to actual output files.
- Access to the existing advanced device preview under a secondary disclosure.
- The original manuscript remains untouched by compiling.

The browser test used an isolated fictional project and generated real EPUB, DOCX, and PDF files; no cloud submission occurred. Backend tests independently inspect EPUB mimetype, DOCX archive members and PDF signatures.

**Preview limitation:** CSS device dimensions approximate reading environments; they do not certify Kindle, retailer, screen-reader or physical printing behavior.

## 3 — Existing capabilities incorporated

Part 4 is not a wholesale rewrite of already functioning author workflows. It unifies the existing Production Preflight (with author waivers), Preview Studio, Cover Studio, Audiobook Studio, Distribution and Submission panels, and Project History. Their previous functions and safety boundaries remain available.

## Verification

- Frontend TypeScript/Vite production build passed; existing bundle warning remains.
- New backend coverage checks data isolation, actual manuscript lineage, explicit consent, invalid acknowledgment, stale manuscript/metadata/asset state, archive corruption, and valid local EPUB/DOCX/PDF exports.
- Browser automation traversed all six stages, inspected issues, tested a local-only author review confirmation, and verified a persisted receipt.
- Browser automation exercised reader preview, device modes, format preset selection, local compile confirmation and three generated formats.
- Width/overflow checks passed at 390px mobile, 900px tablet and 1440px desktop for the new surfaces.
- All screenshots are actual running application captures from **The Ashen Coast — Synthetic Editorial Review**. No private manuscript was modified.

## Actual captured screenshots

- [Publishing Desk](screenshots/part4-synthetic/01-private-publishing-desk.png)
- [Interior milestone](screenshots/part4-synthetic/02-interior-compile-milestone.png)
- [Cover and identity](screenshots/part4-synthetic/03-cover-and-identity.png)
- [Distribution readiness](screenshots/part4-synthetic/04-release-distribution-readiness.png)
- [Recovery and history](screenshots/part4-synthetic/05-recovery-history.png)
- [Editorial readiness](screenshots/part4-synthetic/06-production-readiness.png)
- [Publishing Desk — mobile](screenshots/part4-synthetic/07-mobile-publishing-desk.png)
- [Release check — mobile](screenshots/part4-synthetic/08-mobile-release-check.png)
- [Publishing Desk — tablet](screenshots/part4-synthetic/09-tablet-publishing-desk.png)
- [Author review confirmation](screenshots/part4-synthetic/10-private-signoff-confirmation.png)
- [Private review recorded](screenshots/part4-synthetic/11-review-recorded.png)
- [Interior Atelier presets](screenshots/part4-synthetic/12-interior-atelier-presets.png)
- [Actual chapter preview](screenshots/part4-synthetic/13-private-book-preview.png)
- [Phone reader simulation](screenshots/part4-synthetic/14-phone-book-preview.png)
- [All-format compile preset](screenshots/part4-synthetic/15-complete-compile-preset.png)
- [Interior Atelier — mobile](screenshots/part4-synthetic/16-mobile-interior-workshop.png)
- [Interior Atelier — tablet](screenshots/part4-synthetic/17-tablet-interior-workshop.png)
- [Confirm generation](screenshots/part4-synthetic/18-confirm-interior-build.png)
- [Generated EPUB/DOCX/PDF](screenshots/part4-synthetic/19-formats-generated.png)

## Remaining pre-stable acceptance gates

This is a strong Part 4 integrated review build, **not the stable release**. The following requirements remain deliberately open:

1. Broader live author usability tests, independent assistive technology and keyboard-only audit, high zoom and very large project performance.
2. Installer/update reliability and release provenance on a clean non-developer Windows machine.
3. Stronger semantic continuity and true local long-form model performance certification; prior Part 1 inference throughput remains unresolved.
4. Retailer acceptance, genuine printed proofs and accessibility auditing of exported EPUB/PDF/DOCX are external validation requirements; internal checks are advisory.
5. Existing Submission, Cover and Audio workflows are linked; a full integrated end-to-end real retailer deployment has not been attempted and no files have been automatically sent.
6. Cross-tool concurrency, recovery after interrupted compiles, hardening of every legacy endpoint and nuanced export freshness beyond file existence remain future work.
7. The requested **full Help Wiki and step-by-step floating Ember companion guidance** are registered in [the stable release requirement](STABLE_RELEASE_HELP_WIKI_REQUIREMENT.md). They must be authored and acceptance-tested against the actual frozen stable UI, not a shifting feature preview.

## Guided author acceptance path

1. Select a project and open Publish. The Publishing Desk appears, with six milestones and actual source-linked readiness.
2. Inspect one editorial warning and follow its source or detailed review stage.
3. Open Book Interiors, choose the Digital Edition preset and build a private reading preview.
4. Switch simulated Phone/Tablet/Print devices and navigate between chapters.
5. Select Complete Set and explicitly confirm a local export of EPUB/DOCX/PDF.
6. Open the actual exported files, compare chapter order and formatting and confirm files are in local exports.
7. Visit Cover and Release milestones. Inspect available cover assets, edition settings and locally sourced retailer validation.
8. Return to Publishing Desk, record a review note with a confirmation and observe the new dated local receipt.
9. Change manuscript or release metadata and verify that prior review receipt is now stale.
10. Open Recovery, create a checkpoint and demonstrate restoring it safely in a disposable synthetic project.

The release cannot be marked stable until the open gates are resolved and the exact final UI is documented for the Ember guided help engine.
