# Stage 2 — Chunk 5 / Character Evidence Atlas (2026-11-14)

Status: first deliverable implemented; not a full 80-book semantic characterization model.

## Motivation

The Destroyer reference collection now has 80 immutable source snapshots and 1,723 verified EPUB structural entries, but initially only three author-registered characters: Remo Williams, Chiun, and Harold W. Smith. The existing local models did not pass the strict ten-question source-quote benchmark. Automatically declaring personality, motives, relationships, reader knowledge or plot continuity from raw model output would make the Canon Graph unreliable.

## Delivered

- **Character Minds → Where the books mention your characters**: actual name and author-defined alias matching across original source snapshots, per-volume counts, compact visual distribution, balanced quoted samples and exact immutable character offsets; sample section labels use the confirmed EPUB index. Author can open the original source.
- For a selected character, a separate nearby-name measure counts literal appearances of other registered characters within 250 characters. This is expressly *not* proof of an interaction, relationship, shared scene, or speaker attribution.
- **Character Minds → Find more possible character names**: a separate *review-only* candidate discovery tool uses capitalization and multi-book frequency. It excludes known names/aliases, checks direct source positions and shows author-inspectable quotes. Search is available across all candidate strings, not only the top 60.
- Explicit author selection can register a candidate as an empty character entity; the action does not approve a single fact, event, belief or relationship. Simply scanning candidates makes no changes.
- Both tools use local imported text only; no LLM calls, no cloud transfer, no source text stored in Git. The review-only detector does not claim capitalization implies personhood.
- API routes: `GET /api/series/{id}/character-presence?entity_id=...` and `GET /api/series/{id}/name-candidates?q=...`. Series/entity isolation, bounds, provenance and input validation are tested.

## Real live corpus results

The three already-registered character labels/aliases yielded:

| Character | Literal matches | Books with matches | Query runtime |
| --- | ---: | ---: | ---: |
| Remo Williams | 45,036 | 80/80 | 3.24 s |
| Chiun | 21,739 | 80/80 | 3.62 s |
| Harold W. Smith | 810 | 80/80 | 3.45 s |

Name discovery scanned all 80 sources in 3.12 s and found **896 repeated-capitalization candidate strings**, 60 shown initially; not all are characters. These counts depend on registered aliases and heuristic filters. Counts include narration, remembrance, dialogue, back matter or other contexts: they are not scene appearance statistics.

The application does **not** register the 896 candidates or approve any source fact automatically. The already-existing three staged event review leads remain unapproved.

## Verification

- Six new backend tests covering source-offset integrity, similar-name boundary prevention, author-registered-name exclusion, searchable candidates, series isolation and no automatic registration.
- Full Series regression suite: **176 passed** with one expected synthetic duplicate-mimetype ZIP warning.
- TypeScript/Vite production build and Python lint passed.
- Live 80-book API probes verified all three actual registered characters and a successful read-only name-candidate scan.
- Browser smoke validates Character Minds, original event review, model controls and verified EPUB recovery; new Character Minds checks confirm the character map and name-candidate review panel without mutating canon.

## Next release gates

Character-level beliefs/motives remain deliberately empty until source-cited assertions are reviewed. Next research work should focus on author-graded scene/POV attribution and quote-level ambiguity tests, then higher-quality model evaluation before any attempt to process all 80 books automatically. Release certification still requires independent author review; raw name matches cannot satisfy the 38-gate author standard.
