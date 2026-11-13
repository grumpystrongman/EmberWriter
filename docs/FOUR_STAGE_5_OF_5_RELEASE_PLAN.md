# EmberWriter — Four-Stage 5/5 Build & Certification Plan

**Date:** November 13, 2026
**Release policy:** NO RELEASE until **all 38 gates independently earn 5/5** at the exact release commit, with passing machine evidence AND independent experienced-author and expert review. An automated agent does not substitute for a real human signoff.

The scorecard lives at `frontend/src/release-gates.ts` and can be checked in the app under **Tools → Release Lab**. The five domains are Author Experience (10), Story Intelligence (10), Safety & Infrastructure (5), Publishing & Delivery (4), and Professional Author Features (9). IDs are immutable unless a reviewed schema migration changes the scorecard. All existing UX, 80-book continuity, and professional-feature requirements are included.

## Stage 1 — Measurable standards, safe reference ingestion and Release Lab

**Status: implementation in review, not 5/5 certified.**

**Scope:** combine every former scorecard; preserve unalterable release gates; show a professional interactive evidence dashboard; harden bulk and single-EPUB preflight against unsafe archive structures; add a source-backed 80-volume character appearance atlas; integrate the reviewer checklist and automated test routines.

**Exit tests:** exactly 38 unique gates; missing evidence fails certification; synthetic/AI-only self-attestations never authorize release; frontend production builds; targeted safe-import and FTS search regression passes; local browser screenshots show UI at 390px and 1440px; no copyrighted source passages enter Git. Adversarial mimetype sizes, duplicate mimetype and inner decompression cases must be rejected without import mutation.

**Known limits:** a credible quality measurement framework is NOT the same as 5/5 performance. Named character mentions are NOT narrative knowledge. Independent author review, full accessibility, entire backend regression and long-form local-model performance are separate tests.

## Stage 2 — Genuine cross-book story intelligence

**Status: not yet accepted / build next.**

**Scope:** parse ordered source into granular scene/event citations; extract **proposed only** story facts, motivations, beliefs, secrets, promises and relationship events; track world truth, point-of-view knowledge, reader revelation and as-of book/scene chronology separately; add author approve/reject/undo with cited original positions; build conflict and causal reasoning with accurate abstention. Never silently promote claims to canon.

**Acceptance:** at least 50 author-reviewed cross-book golden Destroyer questions, including temporal cutoff and negative tests, with reliable source citations. Include multi-book cause-and-effect, contradictions, character-knowledge shifts, consent/boundaries when relevant, and false-positive abstentions. Real local model timeouts must be bounded and reported correctly. All source text remains on the PC.

**Primary gates:** SER-02 through SER-10, UX-04/06/07, CRAFT-01/04/05, ENG-02.

## Stage 3 — Professional novelist's daily writing workflow

**Status: not yet accepted / after Stage 2.**

**Scope:** one coherent Plan/Analyze → Writer → Revision experience; context-sensitive manuscript inspector; Scene Director to real-model drafts, explicit source-aware compare/select/accept, reversible application to manuscript and safe story-state refresh. Simplify mobile, keyboard controls, panels, tooltips and focus. Extend Ember into a complete release-specific offline wiki with real screenshots and truthful step verification. Complete beta-review, research links, writing cockpit, customization, exports and proofing interactions.

**Acceptance:** novelists can complete writing, editing, continuity, research, feedback and publishing workflows without undocumented intermediate steps or lost cursor/project state. Tested selected-edit revert, failed generation, cancellation, and offline help. All screenshots and targets verified on the exact build, including 390/900/1440 widths, 200–400% zoom and keyboard paths.

**Primary gates:** UX-01 through UX-08, UX-10, CRAFT-01 through CRAFT-09, PUB-01 through PUB-04.

## Stage 4 — Real release certification, recovery and external author proof

**Status: blocked until the other stages pass.**

**Scope:** cross-tool atomicity and concurrency; crash/disk-full/migration rollback and multi-window editing; security threat model; real local-model literary and throughput benchmarks; 250K–500K-word series load tests; WCAG 2.2 AA, NVDA, 200/400% zoom and reduced motion; clean Windows installer/update/rollback; EPUBCheck, real reading app/device and print proofs; independent observed author usability testing.

**Acceptance:** every one of 38 gates has reproducible, hashed, same-commit test receipts and **two independent human signoffs** (one author and one expert) stored in the release manifest. The fail-closed CI rejects missing evidence, skipped critical cases, counterfeit/synthetic attestations, stale commits, source leakage or unverified 5/5 claims. Do not tag, distribute or announce a stable build before authorization and all tests pass.

**Primary gates:** ENG-01 through ENG-05, UX-01 through UX-10, SER-01 through SER-10, PUB-01 through PUB-04, CRAFT-01 through CRAFT-09.

## Operating agreement

- Only one stage is considered complete per review; do not silently claim later stages are finished.
- Each stage lands in a separate reviewable commit/PR with test logs, source diffs, synthetic screenshots and an honest updated scorecard.
- The connected real Destroyer reference collection remains local. No archive, excerpt or proprietary manuscript enters the repository, CI or a cloud reviewer.
- An AI-created review or automated UI acceptance can **inform** the score but can never independently confer a full human-validated 5/5.
- **Stage 1 can finish without the product being release-ready**; the final release gate stays locked until Stage 4 verifies 38/38.

## Stage 1 evidence

See `docs/reviews/2026-11-13-unified-release-lab-build.md` for real desktop/mobile screenshots and the Release Lab walkthrough, `docs/reviews/2026-11-13-character-atlas-test.json` for private 80-book research metadata, `scripts/verify_release_scorecard.mjs` for fail-closed certification, and `backend/tests/test_series_bulk_import.py` for importer safety regression tests.
