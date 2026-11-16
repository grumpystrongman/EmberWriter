# Author Experience Review — 2026-11-12

**Reviewer:** EmberWriter Author Experience Reviewer — principal UX/UI critique + experienced working novelist perspective.
**Candidate:** `feature/part-4-publishing-command-deck`, audit based on the 4-part stack at `f30e9b9` plus current cleanup changes (not a frozen release).
**Environment:** isolated synthetic project *The Ashen Coast — Synthetic Editorial Review*, local FastAPI, Vite and Chrome DevTools; 1440 × 900 desktop, 900 × 800 tablet, 390 × 844 phone.
**Evidence:** [14 fresh browser screenshots](assets/2026-11-12/) and [machine-readable DOM / viewport observations](2026-11-12-evidence.json). Captures are from this audit, not Part 1–4 promotional screenshots.
**Verdict:** **Promising author-review build, not yet ready to declare a stable release.** The visual language is substantially more mature than a form-based CRUD interface. The chief remaining problem is creative friction: key author actions are hidden under repeated high-level navigation and oversized hero surfaces.

## Journey evidence — first-time and working-author perspectives

| Step | Actual task or entry | Evidence | Health | Observation |
|---|---|---|---|---|
| 01 | Open a chapter in the writer | [Write desktop](assets/2026-11-12/write-desktop.png) | Working, needs polish | Real manuscript is centered and readable. Raw `manuscript/…md` file path dominates chapter context. |
| 02 | Continue the chapter on a phone | [Write mobile](assets/2026-11-12/write-mobile.png) | Functional, needs polish | Prose is legible without measured horizontal overflow. Formatting commands consume several rows above the text. |
| 03 | Discover editing tools | [Plan desktop](assets/2026-11-12/plan-desktop.png) | Working, extra navigation | Another top workspace plus a four-way planning menu plus an edit sub-menu before reaching actual editorial work. |
| 04 | Access editing on a phone | [Plan mobile](assets/2026-11-12/plan-mobile.png) | Limited first-screen productivity | Navigation and section introduction fill much of the initial viewport. |
| 05 | Run an editorial inspection | [Analyze desktop](assets/2026-11-12/analyze-desktop.png) | Working, fragmented | The separate Analyze workspace has overlapping critique/revision concepts with Plan → Edit & Review. |
| 06 | Access Analyze on a phone | [Analyze mobile](assets/2026-11-12/analyze-mobile.png) | Functional, dense | Many controls, report counts, sub-views and labels compete inside the narrow width. |
| 07 | Inspect private publishing workflow | [Publish desktop](assets/2026-11-12/publish-desktop.png) | Polished, below-fold friction | Publishing milestone selector plus a large hero put actionable evidence low in the first viewport. |
| 08 | Prepare a book on a phone | [Publish mobile](assets/2026-11-12/publish-mobile.png) | Good reflow, below-fold friction | No measured page overflow, but the first meaningful milestone content needs substantial scrolling. |
| 09 | See a mid-size publishing view | [Publish tablet](assets/2026-11-12/publish-tablet.png) | Reflows | Tablet layout has no measured horizontal overflow; real edit, validation and proof checks remain separate tests. |
| 10 | Open publishing interior milestone | [Publishing milestone](assets/2026-11-12/publish-interior-milestone.png) | Real interaction | Choosing a milestone changes the inspector; first-time author still needs an obvious next action. |
| 11 | Discover a novel/series universe | [Series desktop](assets/2026-11-12/series-desktop.png) | Rich visual design | The Observatory and Character & Scene Studio are accessible but compete with six other top-level Series panels. |
| 12 | Work with a series on a phone | [Series mobile](assets/2026-11-12/series-mobile.png) | Working, long navigation | Header, series chooser, creation disclosures and multiple nested tabs precede the actual universe. |
| 13 | Inspect manuscript health | [Editorial desktop](assets/2026-11-12/editorial-desktop.png) | Working, below-fold content | The section introduces a full-width hero before the chapter river; metrics begin near the bottom. |
| 14 | Inspect manuscript health on a phone | [Editorial mobile](assets/2026-11-12/editorial-mobile.png) | Working, heavy vertical stack | Real diagnostic content is beyond the first screen behind multiple navigation and promotional elements. |

*Health refers to observed entry behavior, not end-to-end workflow certification. The capture did not execute all manuscript editing, model inference, screen-reader, retail or recovery operations.*

## Scored assessment (1 weak–5 strong; task-unverified areas are not awarded top marks)

| Lens | Score | Supporting evidence and limitation |
|---|---:|---|
| Creative flow | 3/5 | Writer is focused and legible; multiple setup/toolbar/navigation layers before nearby editing/continuity work. Steps 01–04. |
| Discoverability and orientation | 3/5 | Current project and workspace are visible on desktop; Plan vs Analyze editing tools are duplicated across IA. Steps 03,05,06. |
| Mature visual hierarchy | 4/5 | Editorial typography, violet/ink palette, dimensional cards and source-backed features feel professional. Large headings crowd content. Steps 07,13. |
| Interactive depth | 3/5 | Milestone selection, timeline and workspace controls exist; complete live task depth remains beyond this screenshot audit. Steps 10–14. |
| Cognitive load | 2/5 | Nested top-level menus, second-tier menus, third-tier tool tabs, then inner tabs. Steps 03,07,11. |
| Professional novelist usefulness | 3/5 | Strong foundations in story evidence, editorial inspection and export, but source-to-manuscript flow and true causal analysis remain limited. Code and earlier integration gates corroborate. |
| Trust and reversibility | 4/5 | Actual editing APIs retain source hashes, revision history and author signoff; cannot guarantee all legacy writes without global locking. Previous verified tests + current source. |
| Keyboard/mobile/accessibility | 2/5 | No horizontal overflow at the measured widths. Small touch targets and ambiguous icon control names appear in DOM review; no full keyboard/AT audit. |
| Navigation performance | 3/5 | App renders within the local smoke capture; no quantitative large-book stress or interaction latency captured this run. |
| Contextual learning and Ember guidance | 2/5 | Existing floating assistant has a small static guide list in `frontend/src/EmberCompanion.tsx`; release-specific stepwise help is tracked but not built. |

## Highest-impact changes — implement in this order

### UX-001 · P1 · Put the author's next action above the fold
- **Evidence:** [Editorial desktop](assets/2026-11-12/editorial-desktop.png), [mobile](assets/2026-11-12/editorial-mobile.png), [Publish desktop](assets/2026-11-12/publish-desktop.png), [mobile](assets/2026-11-12/publish-mobile.png).
- **Working novelist's cost:** multiple swipes every time they need an actionable chapter graph, export or validation finding. That is time outside the manuscript.
- **New author confusion:** strong brand statements suggest presentation/demo rather than a responsive work surface.
- **Proposal:** compact persistent workspace title and *one task-specific next-action tile*. Reduce visual hero after first visit; optionally allow an expandable introductory hero. Move chapter river / open issues / next build action immediately under primary title. Keep visual craftsmanship in the work instrument itself.
- **Acceptance:** at 1440×900, a chapter river or release milestone plus its primary action is visible without scrolling; at 390×844, at least one meaningful and tappable work action appears within the first viewport. Preserve source evidence and empty states.
- **Files:** `DevelopmentalStudio.tsx`, `developmental-studio.css`, `PublishingDesk.tsx`, `publishing-desk.css`. **Effort:** M.

### UX-002 · P1 · Unify Plan/Analyze edit and review navigation
- **Evidence:** [Plan](assets/2026-11-12/plan-desktop.png), [Analyze](assets/2026-11-12/analyze-desktop.png), [Analyze mobile](assets/2026-11-12/analyze-mobile.png).
- **Novelist cost:** hunting two conceptual review studios, switching context and losing the next intended step.
- **Proposal:** one discoverable **Edit & Review** experience with four clearly differentiated jobs: understand the draft, hear character voices, compare revision, approve/restore. Existing Analyze tools become contextual sub-panels or deep links rather than a competing editorial command center. Keep exact source citations and author-safety flows.
- **Acceptance:** an author goes from selected chapter → health finding → original excerpt → proposed edit → selective acceptance → restore in one visible, backtrackable path, with no ambiguous duplicate label.
- **Files:** `PlanWorkspace.tsx`, `PlanningHub.tsx`, `AnalyzeWorkspace.tsx`, `DevelopmentalStudio.tsx`, workspace navigation. **Effort:** L.

### UX-003 · P1 · Reclaim the phone workspace from navigation and tiny targets
- **Evidence:** [Write mobile](assets/2026-11-12/write-mobile.png), [Series mobile](assets/2026-11-12/series-mobile.png), [Publish mobile](assets/2026-11-12/publish-mobile.png), [Analyze mobile](assets/2026-11-12/analyze-mobile.png).
- **Novelist cost:** slow scene switching, fiddly formatting commands and nested scrolling while writing or reviewing away from a desk.
- **Proposal:** a small author-first mobile navigation bar or discoverable single-page tool drawer, sticky one-line scene title, optional collapsible formatting ribbon, semantic tab groups, consistent >=44px primary touch targets where feasible. Do not hide essential destructive-action confirmations.
- **Acceptance:** move from chapter to Series/Publish/Plan with a labeled and keyboard/screen-reader usable control; first creative action visible on 390px; 200% zoom and reduced-motion checks; no horizontal overflow.
- **Files:** `WorkspaceShell.tsx`, `workspace-shell.css`, editor toolbar, `SeriesDesk.tsx`. **Effort:** L.

### UX-004 · P1 · Replace static Ember hints with release-grounded task help
- **Evidence:** [Write mobile launcher](assets/2026-11-12/write-mobile.png); current `frontend/src/EmberCompanion.tsx` hard-codes a handful of generic guides. Accepted requirement in `docs/STABLE_RELEASE_HELP_WIKI_REQUIREMENT.md` / issue #134.
- **Novelist cost:** an apparent assistant cannot accurately guide the author through the complex, evolving tools.
- **Proposal:** searchable offline wiki with exact release-specific step IDs, screen context and optional focus/highlight. Use explicit author confirmation or visible UI state to advance, never invented button labels or progress.
- **Acceptance:** help for compile EPUB and revert one paragraph works entirely offline on current release; independent consent for any story passages.
- **Effort:** XL; **dependency:** stabilize final UI and versioned control IDs first.

### UX-005 · P1 · Make source-backed scene intelligence a seamless author workflow
- **Evidence:** [Series desktop](assets/2026-11-12/series-desktop.png) and Part 2 documented copy-only scene brief; this audit did not execute a real model-generation and round-trip manuscript transaction.
- **Novelist cost:** excellent planning remains separate from actual prose writing; copy/paste creates continuity drift.
- **Proposal:** explicitly author-approved **Send directing brief to Writer**, with cast and source-context preview, generated scene changes marked as suggestions, and a verified return link to the originating Scene Board. Avoid implicit canon promotion or manuscript overwrite.
- **Acceptance:** scene plan → validated draft → selective author acceptance → source-linked state check across a synthetic book; cancel never writes. **Effort:** XL.

## Additional concrete findings

### UX-006 · P2 · Replace file paths as visible chapter headings
- **Evidence:** [Write desktop](assets/2026-11-12/write-desktop.png), [mobile](assets/2026-11-12/write-mobile.png).
- Current heading prominently displays `manuscript/01-the-letter-beneath-the-door.md`. A novelist thinks in *chapters*, not paths.
- **Proposal:** show `The Letter Beneath the Door` as the title, with a subtle optional breadcrumb / file path inside document details. **Acceptance:** title comes from Binder/source chapter metadata and remains stable through rename. **Effort:** S–M.

### UX-007 · P2 · Consolidate repeated Series navigation
- **Evidence:** [Series desktop](assets/2026-11-12/series-desktop.png), [mobile](assets/2026-11-12/series-mobile.png).
- Eight Series tabs plus inner six Observatory lenses make the mental model harder than it needs to be.
- **Proposal:** visually distinct modes *Explore*, *Direct*, *Verify* and *Library*, with the advanced Series Vault tools in a contextual panel and one prominent current-book selector. **Effort:** M–L.

### UX-008 · P2 · Make generated files' freshness explicit
- **Evidence:** [Publish desktop](assets/2026-11-12/publish-desktop.png); `frontend/src/PublishingDesk.tsx` lists existing artifacts and a current-review receipt, but does not prove each export was compiled from the current manuscript.
- **Proposal:** per-artifact "Created from chapter version [hash/time]" and "Recompile required" states based on source lineage and verified export manifests, not merely filesystem existence. **Effort:** M.
- **Acceptance:** edit a chapter after building EPUB and the old EPUB is visibly marked stale without deleting it.

### UX-009 · P2 · Complete accessibility naming and target audit
- **Evidence:** [machine-readable audit](2026-11-12-evidence.json): visible tiny controls on desktop, some 17×17px checkboxes, and multiple icon controls without distinct context. **Important:** the automated "unnamed" counts include false positives (the browser/hidden menu label detection is heuristic), so do **not** present them as certified WCAG failures.
- **Proposal:** semantic audit of toolbar and dialog controls, keyboard focus management, clear input labels, target-size exceptions only when justified, screen reader pass and explicit status announcement of saves/errors. **Effort:** M.

### UX-010 · P3 · Remove internal development language from author-facing headers
- **Evidence:** [Editorial mobile](assets/2026-11-12/editorial-mobile.png) ("Part III"), [Publish desktop](assets/2026-11-12/publish-desktop.png) ("Part IV").
- **Proposal:** substitute benefit-oriented section labels for internal delivery phases. Release/phase labels belong in About / release notes, not the author's manuscript. **Effort:** S.

## Functional depth: visual design is ahead of the novelist's needs in a few places

- **Character Minds and relationship constellation:** sourced statements and links are valuable; psychodynamic causal interpretation, independent motives and changing relationships remain largely manual or literal.
- **Scene Director:** strong beat/tension editing; single-action Writer handoff and evidence-backed change propagation are still pending.
- **Manuscript Pulse:** honest measurement of length, repetition and speaker phrases, but not yet rigorous semantic character arc or pacing assessment.
- **Publishing Desk:** useful stages, but the author should distinguish local packaging success from actual retailer validation, professional proofing, accessibility and fresh source linkage.
- **Ember Companion:** inviting presence, not yet the stable-release, stepwise help guide the UI promises.

## Release and verification boundaries

- **Observed:** 14 current-run screenshots; desktop, tablet and mobile without *measured horizontal overflow* for the captured pages; interactive publishing milestone navigates between states; current synthetic local backend and frontend. No private author project was inspected.
- **Previously tested, not rerun end-to-end this audit:** safe revision restore, EPUB/DOCX/PDF generation, local release receipts, source-backed author review, four-part backend regression.
- **Not validated:** professional-author field study, complete screen reader or keyboard-only WCAG audit, full 200–400% zoom, clean-PC installer/update, real-world long novel throughput, retailer proof acceptance or reliable local Ollama long-form output.
- **Build cleanup completed in this review branch:** frontend vendor chunk splitting reduces the largest JavaScript chunk below the project's CI budget. This addresses packaging build hygiene, not the author-facing information architecture problems.

## Prioritized implementation order

1. **Design acceptance gate:** collapse Part 3/4 introduction and repeated workspace navigation; show first author action immediately (**UX-001, UX-002, UX-010**).
2. **Author usability:** mobile navigation/toolbar and chapter naming (**UX-003, UX-006**).
3. **Workflow depth:** one-click safe scene handoff and clearer Series modes (**UX-005, UX-007**).
4. **Publishing trust:** per-artifact source version/freshness and targeted accessibility (**UX-008, UX-009**).
5. **Release-specific onboarding:** full local Help Wiki and verified stepwise Ember guidance after the candidate UI is frozen (**UX-004**).

**Overall conclusion:** Mature visual direction achieved; genuine end-to-end author workflow remains the higher-value next investment. Do not tag this build as stable on the basis of attractive screens or the screenshot audit alone.
