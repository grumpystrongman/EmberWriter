# Stage 2 — Chunk 2: Resumable Source Extraction

**Date:** November 13, 2026
**Parent checkpoint:** Stage 2 Knowledge Lab, commit `b9b274b`
**Status:** Working implementation checkpoint; **NOT a certified 5/5** story-reasoning engine.

## What is built

A local-only, explicitly author-operated extraction pipeline for **one selected imported source at a time**. The author chooses an installed local Ollama model and clicks to prepare a persistent job; preparing does **not** run the model. The author then processes **one bounded section (up to 1,400 source characters) per explicit click**. Progress is persisted in the private Series Vault SQLite database.

The new **Series → Verify → Review canon → Resumable private source extraction** panel displays progress, window count, rejected/ineligible candidates, and an evidence list. Results can be moved into the existing author proposal form. That only populates a proposed assertion; it does **not** modify the manuscript, save approved canon, send anything to a cloud endpoint, or infer truth without evidence.

Source passages remain on the Windows machine. A job is isolated by Series Vault, immutable source ID, source SHA-256 and selected model. Starting the same still-active or completed source/model combination resumes that local job rather than creating duplicates. Each persisted candidate is rechecked against the immutable source character positions **after** the model adapter returns, with source, subject, knower, scope and quote continuity verification. Malformed or cross-series candidates are discarded.

Jobs reject concurrent execution with a SQLite reservation; safe retry uses the same source window after model timeout. A lease permits recovery from an interrupted process. Cancellation is available between source windows. Cancelled jobs cannot resume; a new job may be created deliberately.

## Verification performed

- Focused Python regression coverage: resumable multi-window progress; exact source quote; duplicate start; timeout/retry without skipped text; concurrent calls; cancellation; cross-series API isolation; malicious model output rejection; expired lease recovery.
- Existing local model source-suggestion tests remain part of the focused suite.
- Python static/lint checks on the changed modules.
- TypeScript + Vite production build.
- `git diff --check` on the changed files.
- Source text, candidate JSON and user books never committed to Git. Test cases use exclusively synthetic invented prose.

## Honest quality assessment / unfinished scope

This checkpoint **does not** prove reliable semantic comprehension of an 80-book series. It does not run all 80 volumes automatically, and does not independently validate literary psychology, causal relationships, reader knowledge, scene segmentation or prose quality. The existing local model has previously timed out; job-level retry protects the checkpoint but **does not fix model throughput**. The current implementation deliberately requires one author action per section; practical large-library orchestration and safe background queues belong to the next reviewable chunk.

The global 38-item 5/5 certification lock **remains enforced**. The test run validates engineering mechanics, not independent human literary evaluation or accessibility conformance.

## Next working chunk

1. Measure and harden local-model streaming, health, cancellation, throughput and bounded source-queue orchestration.
2. Add trustworthy chapter/scene-boundary metadata and temporal labels without equating EPUB character position with in-world chronology.
3. Develop a reproducible, author-graded cross-book knowledge benchmark (not merely 50 machine-generated retrieval examples).
4. Have the expert UX/novelist agent review actual author navigation, proof-based chronology and false-positive handling; preserve private source text.
