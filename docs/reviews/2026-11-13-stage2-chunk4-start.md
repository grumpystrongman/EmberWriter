# Stage 2 — Chunk 4, first checkpoint: Verified EPUB structure recovery

**Status:** Implementation started; verified author-controlled reindexing slice. Chunk 4 overall remains IN PROGRESS.

## Delivered in this checkpoint

- New read-only original EPUB parser checks the original bounded, untrusted EPUB against the *entire immutable extracted source snapshot*. It rejects different text/editions without attempting fuzzy character remapping. The import order is accounted for; EPUB spine order is used only as an independently sourced reading-order structure.
- Returns exact Unicode character offsets, original EPUB spine item filenames, explicit XHTML heading labels where actually present, an original-EPUB SHA-256 digest and the immutable snapshot hash. Makes no inference about in-world time, reader knowledge or canon.
- Author-visible controls in **Series → Verify → Review canon → Source evidence → Jump to a source chapter or section**: choose original EPUB, preview exact matches, and optionally **Save verified chapter index**.
- The explicit save step rechecks the original EPUB server-side, stores *only* the verified coordinate metadata in local SQLite, and never stores original EPUB bytes. It never replaces imported text, approves canon, alters approved source citations, or rewrites manuscripts.
- The existing source-section API serves author-confirmed exact-spine metadata when present, validating the saved snapshot fingerprint on read. If the metadata is missing or stale, it uses conservative literal-heading detection.
- Tests cover correct exact offsets, unmatched edition fail-closed, cross-series API isolation, malformed EPUB, author save persistence, rejected overwrite, unchanged manuscript and legacy bulk importer safety.

## Verification

- Focused backend regression: **24 passed**, one expected ZIP duplicate-mimetype warning from a malicious-input fixture.
- Frontend TypeScript/Vite production build: **passed**.
- Read-only live Chromium test: all Stage 2 views plus Chunk 4 original EPUB preview/upload affordance **visible** on BarnesPC; requires a file before preview.
- Existing 80-book reference collection was not modified; synthetic tests create temporary isolated series in a pytest data directory.
- Running local UI at http://127.0.0.1:5173; backend at 127.0.0.1:8000, both from the isolated Stage 2 development worktree.

## Limitations and next implementation tasks

1. Recovery is currently **one source at a time, file-selected by the author**. A safe multi-book matching/confirmation flow still needs designing, without reimporting the 80-book original archive over saved sources.
2. EPUB ToC links and interior fragments are not yet stored as a separate, author-reviewed hierarchy; spine items are the only verified boundaries here. Original spine and chapter structure are different when one spine item contains multiple chapters.
3. Local model cold-start/throughput/streaming/cancellation must be measured before batch extraction and automatic scheduling.
4. Evidence-linked scene and narrative event proposals, chronology validation and an author-graded cross-book benchmark remain the rest of Chunk 4.
5. The independent 38-gate release certification stays locked. This checkpoint proves structure recovery mechanics, not literary understanding.
