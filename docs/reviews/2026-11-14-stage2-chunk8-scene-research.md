# Stage 2 — Chunk 8: Source-grounded scene research and author decisions

Date: 2026-11-14
Status: Functional local research and author-classification infrastructure; not an automatic scene/POV understanding model.

## Motivation

Previous chunks could show candidate names, dialogue cues, and rough event leads, but an author had no compact way to inspect a chapter in bounded narrative context before deciding whether a passage was a scene, transition, recollection, dream, or front matter. Treating chapter breaks, typographic separators, or 1,400-character extraction windows as verified scene boundaries would manufacture story structure and damage continuity.

## Implementation

- `series_scene_windows.scan`: deterministic, paged book research windows. Prefer author-confirmed original EPUB section ranges; isolate exact typographic breaks where present. Subdivide long ranges at paragraph boundaries with a target of 5,200 characters and maximum of 8,500. If an original EPUB index is absent, label boundaries as unindexed source/reading windows and **do not** claim chapter verification. Input bounds and a maximum of 1,200 windows per book keep scans finite.
- Recompute each preview from the immutable imported snapshot. Every row carries source ID, verified original source hash, exact start/end character offsets, SHA-256 of the exact passage, original section label if confirmed, length, and literal character-name appearances. Name matches are not proof of presence within a fictional scene.
- `GET /api/series/{id}/scene-windows?book=...&offset=...&limit=...` and `GET /api/series/{id}/scene-windows/{source_id}/detail?book=...&start=...&end=...`: server revalidates that detail coordinates are a valid computed window before sending the bounded original excerpt; arbitrary source offsets are rejected.
- `series_scene_reviews`: optional author-only SQLite review ledger. Staging requires an exact computed window and creates no approved scene. The author may title and classify the passage as scene, transition, recollection, dream, front/back matter, or non-scene; can identify narrative POV and a registered POV character only after verification. Approval requires a meaningful title, explicit non-uncertain kind, and source integrity; no canon graph fact is created automatically. Records can be rejected.
- Portable ZIP backup and restore include the review ledger, reject fabricated source hashes/coordinates or invalid POV entity IDs before any destination series is created, remap source and character IDs into the new independent series, and remain compatible with previous archives missing this optional field.
- New **Series → Explore → Story History → Explore chapter structure and bounded reading windows** workflow. Uses the Chunk 7 compact two-pane ReviewQueue rather than a card stack. Loads only 40 window rows per page; full verified source text is read on selection and the author decisions occupy a collapsible second queue.

## Real Destroyer corpus verification

All 80 original source snapshots already possess exact saved EPUB structural indices (1,723 sections in the collection). The following *bounded research windows* were produced by real API calls after the frontend/backend restart:

| Book | Paged research windows | First 40 indexed beneath original EPUB section | Max excerpt in page | API runtime |
|---|---:|---:|---:|---:|
| 1 | 61 | 40 | 7,781 chars | ~0.20 s |
| 40 | 49 | 40 | 8,087 chars | ~0.61 s |
| 80 | 68 | 40 | 7,163 chars | ~0.19 s |

An independently requested detail of the first candidate in each book returned HTTP 200 and the exact matching range SHA-256. These counts are **not verified scene counts**. They reflect formatting signals and reading-length subdivisions. There are **zero automatically approved scene/POV claims**.

## Verification / safety

- Six synthetic backend tests added: bounded windows, exact EPUB vs unindexed provenance, source-detail/series isolation, separate author decision gate, HTTP review approval/rejection, and ZIP roundtrip including forged range-hash rejection and backward-compatible missing-field restore.
- Focused suite including portability: 17 passed.
- Full Series regression suite: **186 passed** with one expected synthetic malicious-ZIP duplicate-mimetype warning; Python Ruff checks passed; TypeScript/Vite production build passed; 4 release-scorecard tests passed.
- Real-browser non-mutating smoke confirms a Book 80 scene research queue with 40 rows, a complete 5,170-character fingerprint-verified source passage, explicitly disabled auto-scene attribution, source staging affordance, author-review panel, and all prior Series tools. A 390px queue test confirms the inspector stacks after responsive layout settles.
- No imported manuscript content or private original EPUB bytes committed, no LLM, no remote inference, no canon mutation during corpus testing.

## Remaining gap

These windows intentionally **do not** identify actual scene boundaries, viewpoint, speaker truth, character knowledge or chronology automatically. The next milestone should use a small human-annotated gold standard across diverse story structures, then independently test candidate boundary, dialogue-attribution and temporal hypotheses with rigorous abstention/uncertainty behavior before scaling inference to all 80 books. No model should self-approve its own literary claims.
