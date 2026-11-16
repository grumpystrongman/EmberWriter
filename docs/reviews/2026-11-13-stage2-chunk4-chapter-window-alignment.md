# Stage 2 Chunk 4 — Source-structure-aligned extraction checkpoint

Date: 2026-11-13
Branch: feature/stage2-chunk4-epub-structure

## Change

The opt-in **Process next window** command now chooses extraction coordinates using **author-confirmed original EPUB spine boundaries** when a saved exact-match index exists. It never assumes the EPUB's spine order is identical to the text snapshot's import/item order: it uses immutable snapshot offsets and chooses the first strictly forward boundary within a hard 1,400-character maximum.

With no confirmed index, the existing bounded sentence/paragraph splitter is preserved.

- No skipped or duplicated characters across successful windows; exact next offset is persisted as before.
- Every model response remains only an unapproved suggestion with validated source quotes and explicit author review.
- The API returns the last processed source window and how the boundary was chosen.
- The author sees that provenance immediately in the existing Series extraction workbench.
- Source snapshots, imported EPUBs, and already approved canon remain unchanged.
- No automatic model job queue or batch continuation was introduced.

## Verification

- 15 focused tests passed, including a new synthetic multi-document EPUB that confirms no offsets are skipped as the window advances across an exact saved boundary.
- TypeScript/Vite production build and Ruff lint passed.
- Existing Chapter 4 streaming checkpoint separately passed 28 backend regressions, browser visibility smoke, and live Ollama timing.
- The synthetic fixture revealed a real interoperability detail: immutable importer item order need not match spine item order. Tests now intentionally select the earliest positive **source** offset rather than assuming the second spine element is the second stored segment.

## Remaining Chunk 4

TOC and within-document anchors, an opt-in small multi-book index recovery flow, independently graded local-model quality probes, author-controlled batch extraction orchestration with durable pause/cancel, evidence-linked event proposals and cross-book chronology benchmarks.

This remains a partial implementation of Chunk 4, not a certification of literary intelligence.
