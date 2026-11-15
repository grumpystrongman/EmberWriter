# Stage 2 — Chunk 10: Evaluation integrity hardening

Date: 2026-11-14
Status: Committed for independent CI and human review; no 5/5 certification.

## Why this is necessary

Chunk 9 counted every candidate navigation break within a three-character tolerance as a matched gold break, even though a single true scene boundary can only justify one predicted division. This could undercount false positives and inflate precision. It also accepted malformed benchmark case dictionaries without strict label checks.

## Changes

- A gold boundary can match **at most one** navigation candidate; every additional nearby or distant division is a false positive.
- Malformed gold records fail closed before scoring: duplicate or empty IDs, empty passages, boolean/non-integer/out-of-range offsets, non-boolean boundary labels, unsupported POV classes or invalid knowledge labels.
- The report exposes the one matched candidate offset so reviewers can audit per-case alignment.
- New regression tests cover duplicate nearby candidate breaks, extra distant breaks and malformed gold labels.

## Integrity and privacy

The original 12 gold fixture cases and their stated ground-truth labels are unchanged. This is measurement correction, not improved semantic scene understanding. Production scene approval stays blocked; no private manuscript passage or new inference model is introduced. This does not complete the 50-question independently reviewed cross-book standard.

## Verification requirements

Run `pytest backend/tests/test_series_scene_gold.py` in the configured backend environment; run full Series suite, Ruff, and frontend production build via repository CI. Record the observed new baseline and evidence before merging this stacked draft PR. No automatic score or release-gate upgrade is authorized.

## Next steps

1. Recruit independent author-reviewed holdout passages with stable source hashes, book and passage coordinates, and author signoff while keeping originals on the local PC.
2. Evaluate candidate scene/POV predictions against that held-out reference and report per-category misses, false assertions, abstention and model timeout.
3. Build 50 reviewed cross-book continuity questions and maintain 38/38 fail-closed release policy.
