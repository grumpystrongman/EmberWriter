# Part 3 — Developmental Editor and Revision Studio

**Branch:** feature/part-3-developmental-editor-revision-studio, based on Part 2
**Status:** Integrated author-review build, not a public production release
**Date:** November 12, 2026

## Author experience

Part 3 appears under **Plan → Edit & review → Developmental studio**. It reuses the existing local manuscript intelligence and links to the established Editorial Board, Prose Editor, Story Arc Investigator, and Voiceprint Lab. Nothing gets added to author canon by an editorial report.

### Manuscript Pulse

- Visual chapter river and selected-chapter inspector with actual words, average sentence length, chapter-length outliers and mechanical findings.
- Mechanical and length filters; no invented literary scores.
- Evidence-based opening, ending and quoted-dialogue review prompts, linked back to the authored manuscript.
- Source-linked repeat phrases and unresolved author-managed narrative promises.
- Direct paths to deep local-model narrative inspection, prose fixes, editorial queue and voice comparison.

### Arc & Promise Atlas

- Chapter-by-chapter character and motif presence matrix with source line quotations.
- Author chooses which people, objects or phrases to follow (up to 30).
- Existing author-owned plot promise ledger shown without automated interpretation of its resolution.
- Literal mention does not claim plot agency, thematic importance, emotional change or an earned payoff.

### Dialogue Studio

- Visual speaker cards, quotation timeline and cited lines.
- Speaker attribution only where an explicit speech tag immediately identifies the speaker. Otherwise: Unattributed.
- Per-speaker quoted-word totals, mean quote length and vocabulary samples for editorial comparison.
- Does not infer dialogue subtext or declare a character voice authentic.

### Revision Workbench

- Side-by-side original and alternative manuscript paragraphs.
- Author can rewrite multiple paragraphs while individually checking only those to accept.
- Two-step confirmation before any change reaches disk.
- Backend validates project, editable manuscript path, source SHA-256, paragraph identifiers and edit boundaries.
- Unselected paragraphs are preserved. Saving creates an original snapshot plus database revision records using the existing atomic-save system.
- Revision history offers explicit two-step restoration of an earlier version, guarded by a fresh SHA-256 and creating another recoverable version.
- Book Studio candidates remain in their existing approval flow, not silently rewritten here.

## How everything flows together

Local project manuscript → existing Manuscript Intelligence → visual health and arc readings → direct cited passages → optional established editorial tools → author paragraph alternatives → selective approval and confirmation → source fingerprint validation → archived original and atomic file save → revision history and reversible restore.

## Verification

- TypeScript/Vite production build passed.
- Focused backend tests cover project isolation, original preservation, selected edits, duplicate/stale changes, explicitly attributed speech, and version restoration.
- Actual Chrome browser flow exercised Manuscript Pulse, motif tracking, Dialogue Studio and the Revision Workbench.
- A browser-driven revision changed exactly one checked paragraph in a synthetic manuscript; unselected paragraphs remained unchanged; the original was archived.
- A separate browser-driven test restored that original and confirmed a new revision log entry.
- Layout checks passed at 1440px desktop, 900px tablet and 390px mobile without measured page or studio horizontal overflow.
- The synthetic demo project was The Ashen Coast — Synthetic Editorial Review. No private user manuscript was used.
- Full regression suite: **657 passed, 6 skipped, zero failures** (November 12, 2026). Ruff passed for new backend files; TypeScript/Vite production build passed with pre-existing bundle and Harper.js warnings.

## Actual application screenshots

- [Manuscript Pulse](screenshots/part3-synthetic/01-manuscript-pulse-desktop.png)
- [Chapter evidence and metrics](screenshots/part3-synthetic/02-chapter-inspector-desktop.png)
- [Arc & Promise Atlas](screenshots/part3-synthetic/04-arc-atlas-tracked.png)
- [Narrative evidence](screenshots/part3-synthetic/05-arc-evidence.png)
- [Dialogue Studio](screenshots/part3-synthetic/12-dialogue-studio-desktop.png)
- [Speaker comparison](screenshots/part3-synthetic/13-dialogue-speaker-comparison.png)
- [Revision Workbench](screenshots/part3-synthetic/06-revision-workbench.png)
- [Select an individual edit](screenshots/part3-synthetic/15-revision-selected-diff.png)
- [Explicit approval](screenshots/part3-synthetic/16-revision-confirmation.png)
- [Restore an earlier version](screenshots/part3-synthetic/18-restore-confirmation.png)
- [Mobile revision](screenshots/part3-synthetic/08-mobile-revision.png)
- [Mobile manuscript health](screenshots/part3-synthetic/09-mobile-pulse.png)
- [Mobile dialogue](screenshots/part3-synthetic/14-dialogue-mobile.png)
- [Tablet arc atlas](screenshots/part3-synthetic/11-tablet-arcs.png)

## Scope boundaries and next release gates

1. Metrics and quotation matching are reproducible local diagnostics, not a fully semantic developmental critique of the entire novel. Opt-in deeper work is delegated to the already existing Story Arc Investigator; local-model performance remains a separate unresolved Part 1 issue.
2. There is no arbitrary quality, tension goodness or dialogue authenticity score. Such scores would not be supported by these measurements.
3. Paragraph editing supports independently tracked manuscript Markdown/text files. Rich-text documents and Book Studio candidates retain their established approval workflows.
4. Stale-source guards and a lock protect this workflow, but a shared lock across all other legacy manuscript write endpoints remains future concurrency hardening.
5. Screen-reader certification, high zoom and thousand-chapter usage have not been independently validated; browser visual smoke tests are not comprehensive accessibility certification.
6. This feature branch is stacked on the previous unmerged feature branches. Do not treat this as merged into main or a shipped public release.

## Author acceptance exercise

1. Open the new studio from Plan → Edit & review.
2. Select a chapter in the rhythm river and inspect opening/ending evidence.
3. Track a character or motif and open a cited excerpt.
4. Compare tagged and untagged dialogue.
5. Rewrite two paragraphs, approve only one, and verify the original was archived.
6. Restore the prior version and verify the restoration is itself recorded.
