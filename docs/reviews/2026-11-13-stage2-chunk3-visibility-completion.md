# Stage 2 Chunk 3 — Visible story intelligence completion gate

Date: November 13, 2026
Branch: `feature/stage2-chunk3-visible`
Scope: Visibility and honest empty-state readiness, **not** certification of complete literary cognition.

## Delivered

- The Series workspace now exposes **Knowledge Lab** as a first-level author workflow button.
- On an imported series with no reviewed assertions, **Universe**, **Character minds**, **Plot threads** and **Story history** render a non-fictional evidence onboarding surface. It reports actual source counts, exact counts of unsaved deterministic pattern leads, and short cited previews. It provides direct **Explore source discoveries** and **Review or add canon evidence** controls.
- **Model Lab** remains interactive: shows installed local model choices and offers an explicit three-scene benchmark; the app never runs costly model inference merely to fill a view.
- A safe local Windows launch script selects the new source worktree and explicitly reuses the existing private data directory without modifying the unfinished main checkout.
- No existing manuscript, approved canon assertion or private EPUB content was written into Git.

## Live checks on BarnesPC

- Local frontend port 5173 and backend port 8000 confirmed running from the **new Stage 2 worktree**, not the older Part1 verification directory.
- Chromium DevTools Protocol smoke test opens a temporary tab and validates every named lens. No data is mutated.
- On the real 80-volume continuity reference collection, four evidence panels displayed **80** scanned source snapshots, **9 unapproved leads** and **0** skipped sources. The **Explore source discoveries** button led to the Discovery page with nine real leads.
- Model Lab loaded **15 eligible installed local models** and enabled the **Run three-scene test** button. Generation was intentionally not invoked by the UI smoke test.
- On the separate four-book synthetic Series Vault fixture, **Knowledge Lab** displayed **27 approved claims** across nine lenses; the navigation click works.
- Focused backend suite: **81 passed**, covering source structure, local model status/probes, extraction jobs, knowledge lab, discovery and story state.
- TypeScript/Vite production build passed, and `git diff --check` passed.

Reproducible read-only browser test:
`node scripts/stage2_visibility_smoke.mjs`
It requires an already-running debug-enabled Chromium on local CDP port 9227.

## Not claimed or silently automated

- The 80-volume corpus still has **zero author-approved canon assertions**. Therefore character minds, relationships, plot lifecycle and history cannot responsibly be marked populated; evidence previews are leads, not accepted truth.
- Local-model inference quality remains unverified for the current model set; the three separately documented Chunk 3 synthetic model probes did not pass. Installed model counts establish availability, not quality.
- The EPUB importer may flatten original ToC/spine/chapter boundaries. This is an ingestion-metadata limitation; *source offset is not narrative time*.
- No bulk model extraction, inference queue, 50-question author-graded study or full 5/5 release gate certification has been asserted.

## Next chunk contract

1. Safely preserve/recover EPUB ToC/spine/chapter boundaries with exact source offsets and edition fingerprints; review before any reindexing of existing private books.
2. Prove bounded local model generation with cold-start, streaming, timeout, cancellation and throughput measurements before enabling automatic queues.
3. Implement resumable **opt-in** per-source/book extraction scheduling and source-grounded scene/event proposals that remain unapproved until author review.
4. Run cross-book author-scored chronology, knowledge and contradiction cases before unlocking literary-quality claims.

**Decision:** User-facing visibility/current-chunk navigation gate passes. **Stage 2 literary-intelligence completion and global release-certification gates remain blocked** and are explicitly owned by the next chunk.
