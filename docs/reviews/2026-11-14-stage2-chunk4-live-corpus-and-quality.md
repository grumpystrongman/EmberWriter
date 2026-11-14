# Stage 2 Chunk 4 — Live corpus indexing and synthetic model-quality checkpoint

Date: 2026-11-14
Branch: `feature/stage2-chunk4-epub-structure`
Status: Chunk 4 **in progress**. The provenance/indexing work is verified; literary intelligence release remains blocked.

## Delivered

- Exact-match EPUB spine documents and nested ToC fragment links, including uniquely resolved legacy named anchors.
- One-book and 80-book original EPUB archive recovery, all-or-nothing, requiring full immutable snapshot match before saving local metadata.
- Author-initiated, source-specific extraction checkpoints now honor verified internal boundaries.
- The existing extraction workbench additionally supports **up to three** sequential, individually committed bounded windows per explicit author click. An author can stop after the current window. The implementation never schedules background scanning, auto-approves canon, or writes to manuscripts.
- Five predeclared, synthetic local model-quality checks: literal relationship, character belief vs. world truth, knowledge cutoff by book, event/state transition, and untrusted fictional instructions. Each scored response must match both the exact answer and an exact supporting source quotation. Each case is 22-second bounded and the complete suite is 115-second bounded; browser disconnect cancels the active work.
- UI for those checks in Model Lab and Knowledge Lab; no private source text ever sent by the benchmark.

## Real 80-book source recovery: completed safely

Found the author's already-imported original collection ZIP on BarnesPC. Compared it **read-only** against the live Series Vault, then performed the explicitly authorized atomic metadata-only confirmation. Independent post-save GET requests checked each of the 80 book sources.

| Metric | Confirmed |
| --- | --- |
| Archive EPUBs | 80 |
| Full exact snapshot matches | 80/80 |
| Mismatched / empty books | 0 |
| Indexed structural sections | 1,723 |
| Spine documents with explicit headings | 1,597 |
| Other spine documents | 109 |
| Uniquely matched ToC fragments | 17 |
| Saved indexing records after confirmation | 80/80 |
| Approved canon from this operation | 0 |
| Manuscript replacement | None |

The private archive, EPUB text and author identity must never be committed to the public repository.

## Live local-model comparison (synthetic-only, NOT author-rated)

- **llama3.2:3b:** 4/5 exact question + quote cases passed; the last case had the correct answer but the wrong quotation. ~7.54 s total for the five cases at that time.
- **qwen3.5:4b:** 0/5, with five 22-second local timeouts (~110 s total) on the same workstation. A separate single-case request with thinking disabled still timed out at 20 seconds. This is a **runtime/environment result**, not a permanent assessment of the architecture or model family.
- Model detection alone does not authorize extraction quality. No model achieved the strict 5/5 gate.
- These cases are not sufficient to certify cross-book reasoning, temporal identity, scene causality, narrative psychology, writing quality or adversarial literary ambiguity.

## Verification

- Extended targeted backend regression: **111 passed**, one expected duplicate-mimetype ZIP fixture warning.
- Frontend TypeScript/Vite production build: **passed**.
- Ruff check and Git whitespace checks: **passed**.
- Read-only live Chromium smoke checks verify all original five Story Observatory lenses plus Model Lab streaming and five-case quality controls, 27 approved assertions in the separate synthetic four-book fixture, and both original EPUB recovery controls.
- Persistent uncommitted audiobook work in the main checkout remains isolated, unchanged.

## Remaining Chunk 4

1. Author-reviewed, temporally meaningful scene/event proposals with exact source evidence, reference book and uncertainty.
2. More robust model selection and failure recovery for scene/event extraction; strict local evidence probe failures currently block any claim of production-grade inference reliability.
3. Cross-book author-scored benchmark of chronology, knower state, contradiction and payoff resolution, with missing-source abstention.
4. Durable opt-in continuation/pause across multiple sources without surprise background execution, plus safe author-reviewed acceptance workflow.
5. Full release gate and UI end-to-end tests after acceptance of all above.

Do not mark Chunk 4 complete or unlock automatic canon approval based only on the new structural coverage.
