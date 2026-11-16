# Chunk 4 — Exact EPUB ToC fragment recovery

Date: November 14, 2026
Branch: feature/stage2-chunk4-epub-structure

## Delivered

- Original EPUB ToC links are traversed through nested ebooklib ToC structures.
- Uniquely matched in-document ID and legacy named anchors are resolved to character positions using the exact BeautifulSoup text-node concatenation used by the immutable importer snapshot. No fuzzy string search, invented positions, or external link access.
- Each source is compared in full before offsets can be displayed or saved. Different editions fail closed. External links, missing items, ambiguous duplicate IDs, malformed URLs, repeated offsets and anchors lacking grounded text are rejected.
- An original spine document can contain several ToC sections. Both are retained, with independently grounded provenance and bounded per-source coordinates, up to the existing 400-section ceiling.
- The source navigator displays ToC links distinctly, and active position selection prefers the narrower exact ToC section when it overlaps a spine document.
- Existing author-triggered one-EPUB or all-matching-collection ZIP confirmations store verified ToC coordinates alongside spine metadata. Nothing updates private books until the author confirms the exact source.
- Source extraction already respects any author-confirmed offsets, including new ToC boundaries, within a hard 1,400-character model window.

## Verification

- 22 focused backend tests passed, including nested ToC mapping, duplicate anchors, wrong edition, saved-structure persistence, API active-position selection, extraction boundary usage, collection matching and author confirmation.
- Ruff checks and TypeScript/Vite production build passed.
- The 80-book private Destroyer series has NOT been reindexed or modified.
- ToC labels establish publication navigation only, never story chronology, implied causality, reader knowledge, or canon.

## Remaining Chunk 4

Independently graded local model-quality and cross-book continuity tests, evidence-linked scene/event proposals, and explicitly scheduled author-controlled multi-source extraction with durable pause/cancel remain unfinished. Do not unlock auto-canon approval or bulk extraction based solely on TOC accuracy.
