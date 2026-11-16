# Chunk 4 — Multi-book original-EPUB structure recovery checkpoint

Date: November 13, 2026.
Branch: `feature/stage2-chunk4-epub-structure`.

## Implemented

The original collection can now be reexamined through a **read-only EPUB ZIP preview** and a separate **explicit author confirmation**.

- Open **Series → Verify → Review canon → Source evidence → Jump to a source chapter or section → Recover chapter indexes for a series ZIP**.
- Provide the original numbered EPUB ZIP, up to 150 EPUBs and 60 MB. A safe archive preflight rejects traversal and unsafe members.
- Match each book to an existing source by **volume ordinal AND original source filename**; then reconcile each EPUB's entire extracted text against its immutable source snapshot.
- Preview per-book matching and section counts. Any missing/mismatched book blocks the whole save; confirmation is all-or-nothing.
- Explicit confirmation reruns all checks server-side, then commits verified structural coordinates with source and EPUB fingerprints in **one SQLite transaction**.
- Original EPUB bytes are never stored, manuscripts are never reimported, canon remains unchanged, and source coordinates are never construed as story chronology.
- Supports a subset archive: all EPUBs in the submitted ZIP must match; it does not require the archive to contain every volume in the Series.
- Existing one-book recovery remains available.

## Verification

- Focused backend tests **26 passed**, one expected warning from malformed duplicate-mimetype ZIP fixture.
- Covers read-only preview, successful two-book atomic indexing, mixed-edition all-or-nothing refusal, incorrect filename, traversal rejection, API isolation and manuscript preservation.
- TypeScript/Vite production build passed, Ruff lint passed.
- Live browser verified the EPUB collection recovery is discoverable beneath the source navigator and that its preview button remains disabled until the author selects a ZIP. Existing Stage 2 views and streaming controls passed the smoke script.
- The live private 80-book library was NOT modified or auto-indexed. The only full indexing proof used synthetic volumes and temporary pytest storage.

## Remaining Chunk 4 gates

1. Restore inner EPUB ToC fragment anchors (current verified indexes are source spine documents with explicit XHTML headings where present).
2. Independent author-scored model reliability tests and model-specific extraction throughput/recovery before advancing beyond single-window opt-in extraction.
3. Evidence-linked scene/time proposals with reviewer approval; batch scheduling with durable pause/cancel only after quality gates.
4. Cross-book chronology/contradiction benchmark and end-to-end author validation.

This checkpoint makes 80-book structure recovery accessible without repetitive one-file-at-a-time uploading; it does **not** mean the 80 private books have been indexed yet.
