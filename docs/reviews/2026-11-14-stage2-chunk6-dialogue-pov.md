# Stage 2 / Chunk 6: Dialogue and Viewpoint Evidence (2026-11-14)

Status: author-reviewable dialogue candidate detection implemented; **not** automatic scene, viewpoint or speaker understanding.

## Delivered

- New `GET /api/series/{series_id}/dialogue-leads?book=N` scans preserved immutable text for short quoted strings with explicit nearby character names and speech verbs. Supports bounded pages, optional known-character filters, exact quote and context offsets, snapshot hash and verified original EPUB section labels.
- Found real candidate leads in Destroyer Book 1 (**70**), Book 40 (**218**) and Book 80 (**182**) in a direct local backend check. Each call took approximately **0.3–0.5 s**. Counts represent **speech-cue candidates only**, not dialogue turns, scene boundaries, reliable speakers or narrator truth.
- `series_dialogue_reviews` is a distinct SQLite author ledger: stage a reproducible quoted candidate, explicitly select the verified speaker and optional narrative framing (first-person, third limited, third omniscient, mixed or unknown), add notes and approve/reject. All proposals begin unapproved, nothing is auto-promoted to the canon graph, and no entity is created.
- The **Character Minds → Research dialogue and POV clues** panel exposes reviewable source excerpts, source navigation, per-book paging, character-name filters and the standalone decision ledger.
- ZIP backup and restore include author dialogue decisions, securely validate the exact source hash/quote coordinates, remap speaker and source IDs into an independent new series, and reject tampered quotes or invalid speaker IDs before creating the destination series. Old archives without the new field remain importable.
- No novel excerpts or original publication files are included in Git. The original 80-book snapshots are unmodified. The scan operates entirely locally, with no inference vendor involved.

## Limitations

The attribution is deliberately a weak clue detector: proximity to `said`, `asked` or related verbs does not prove the named character said the quote. Other characters, nested dialogue, flashback narration, pronouns, transcribed interviews, other languages, or unreliable accounts can deceive it. The author must inspect each quote before verifying a speaker. The optional POV class is entered by the author; there is **no reliable automated POV determination**.

There is no claim of scene segmentation, author-grade emotional arcs, motive analysis, or exhaustive 80-book knowledge. Local model reliability remains below the synthetic evidence quality threshold, so model-generated canon is not promoted.

## Verified

- Three synthetic dialogue tests check exact literal coordinates, failure on unsupported sources/foreign series, separate author approval, and no automatic canon updates.
- Additional portable ZIP roundtrip test checks author approval retention and source/speaker ID remapping, backward compatibility and forged-speaker rejection.
- Full Series suite: **180 passed**, one expected synthetic malicious-EPUB duplicate-mimetype warning.
- Python Ruff checks and TypeScript/Vite production build passed.
- Real local API checks: Book 1 70 leads, Book 40 218, Book 80 182, no dialogue decisions written to the real corpus.
- A read-only browser smoke check confirms that Character Minds shows 40 paged dialogue leads and the author-only stage control, alongside the pre-existing Series workspaces.

## Next

Build *independent* scene/POV gold-standard annotated samples across several literary narrative types. Only adopt a local speaker/POV model when it consistently supports exact evidence and abstains on ambiguous or unreliable narrators. Contrast explicit text with character beliefs and false narrations before accepting continuity decisions.
