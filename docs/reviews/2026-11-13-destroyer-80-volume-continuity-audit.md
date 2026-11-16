# Destroyer 80-Volume Import, Source Search and Continuity QA

**Regression verification:** **677 passed, 6 skipped, 0 failures**; Python Ruff passed on modified import/search/routes/tests; TypeScript/Vite production build passed. The two attempted local Ollama continuity-review critics timed out without output, so neither is counted as a completed independent model review.

**Run date:** 2026-11-13 · **Site:** local EmberWriter at `http://127.0.0.1:5173/` on the authorized Windows test computer · **Branch:** `feature/ux-scorecard-hardening` · **Disposition:** TEST-READY FOR HUMAN CONTINUITY EXPLORATION, **NOT** 5/5 narrative intelligence certification.

**Privacy:** The user's books, original ZIP and source text live exclusively in the PC's private test-data directory. Original archive: Windows Downloads. The Series Vault sources and browser screenshots containing book prose stay local, ignored by Git. This report contains only metadata, timings and acceptance results. Test server and frontend bind to `127.0.0.1`.

## Source and import verification

- The uploaded 21,149,915-byte ZIP is byte-identical to the Windows Downloads ZIP: SHA-256 `83e3e299b715c743c3874a595dc3da8eb36db1088e91ed2590978220cb017e33`.
- Archive consists of **80 valid EPUBs in volumes 001–080 with no missing or repeated ordinals**, plus one irrelevant catalog sidecar (ignored).
- All 80 EPUB containers passed `zipfile.testzip` and declared `application/epub+zip`. The supplied EPUB OPF metadata declares one author credit across all books.
- A new local-only **bulk numbered-EPUB ZIP import** API and Series Desk interactive upload were exercised on the isolated synthetic test environment.
- Series: **The Destroyer - 80-Book Continuity Lab**; ID `11d2558e7e1248298d1454ab6e906883`. It contains **80 ordered volumes / 80 source snapshots** and 23,757,877 imported text characters in the recorded run.
- Measured import time **16.398 seconds**. Source SHA-256 and exact offsets were sampled in volumes 1, 20, 40, 60 and 80, with full 80-snapshot checks by the automated continuity QA probe.
- No imported book was linked to or written into an author manuscript project. No canon assertion was automatically approved. The existing synthetic author project was not altered.

**Important:** Rights approval is an explicit UI checkbox. The books are provided by the user for their own private local reference test; they are not included in the repo, hosted, or distributed.

## What the automated author/continuity reviewer actually proved

| Test | Outcome | Evidence |
| --- | --- | --- |
| ZIP archive matches supplied original | **PASS** | SHA-256 comparison on both machines |
| Batch import into one private Series Vault | **PASS** | 80 volumes, 80 snapshots, recorded API import |
| Book ordinal ordering | **PASS** | 001–080 exact, no duplicate/missing ordinals |
| Isolated source retrieval | **PASS** | 80 source hashes; sampled read positions 1/20/40/60/80 |
| Offline cross-series evidence search | **PASS** | Remo, Chiun, Smith, CURE, Sinanju + negative search |
| Book 20 spoiler cutoff | **PASS** | 3,170 matching windows for test query, zero results from books 21–80 |
| Book 1 cutoff | **PASS** | All returned matches confined to book 1 |
| Negative query | **PASS** | Nonexistent token returned zero matches |
| Direct source navigation | **FIXED & UNIT TESTED** | Search now passes cited source coordinate, not just first occurrence of term |
| Responsive source UI | **PASS limited** | 1440px desktop and 390px phone browser captures without overflow |
| Safe canonical story understanding | **NOT PROVEN** | Five entities but zero approved story facts; no tested causal interpretation |
| Independent local model literary critique | **BLOCKED** | 9B model timed out at 180s; 3B model also timed out at 75s; neither scored the text |

The archived benchmarks show median selected search response latency well under 0.2 seconds for the warmed, local FTS5 index; these are small-query workstation measurements, not multithreaded stress tests or semantic model performance.

The review agent's decision to abstain from inventing canon while zero facts are approved is **correct** behavior, not success at knowing the story. `Discover` produced nine candidates in the deterministic probe; all remain proposals until the user validates their evidence.

### Current author-specific scorecard

| Dimension | Provisional score | Why it is not 5 |
| --- | ---: | --- |
| Archive integrity and ordered import | **4/5** | Real 80-volume import works, but malformed nested EPUB bombs, interrupted writes, concurrency and repair still need adversarial coverage |
| Source retrieval and citations | **4/5** | Exact matches and coordinates verified; need semantic hybrid search, more robust result grouping and click-through regression in browser |
| Spoiler-safe temporal search | **4/5** | Book 1/20 cutoff tests pass; chapter/scene-level as-of filtering and temporal relationship states not verified |
| Desktop/mobile usability | **3/5** | Search is visible and responsive; oversized hero and series navigation; missing complete keyboard/AT testing |
| Source provenance and author approval | **4/5** | Hashes, local snapshots, no auto-canon; source-to-assertion edit/reject and multi-window persistence need more tests |
| Character psychology and knowledge | **1/5** | Names/mentions are not knowledge, fears, motivations, secrets or event-grounded character beliefs |
| Relationship causality | **1/5** | No character change graph or multi-book relationship evolution extracted and approved |
| Continuity-conflict reasoning | **1/5** | No real approved claim set to compare across 80 novels; no positive/negative contradiction benchmark |
| Local-model long-form reviewer performance | **Not rated / blocked** | Two local Ollama reviewer attempts timed out without producing valid scored output |
| Local source privacy | **4/5** | Loopback and no book text in Git; cross-application permission and secure backup threats still need full audit |

## The experienced novelist / UX agent's prioritized findings

**CRITICAL — story comprehension is not keyword search.** A professional series author wants to ask *what did character X know at Book 12*, *when did a belief change*, *what earlier scene set up this consequence*, and *why would a proposed new scene contradict earlier canon?* The current evidence search can find literal passages, but it cannot answer those questions reliably from the corpus alone. Never market lexical lookup as deep memory.

**P1 — build source-grounded, author-reviewed knowledge extraction.** Ingest book → segment scenes/chapters → derive draft propositions with quote+offset+book+POV/confidence → author review and approve/decline → maintain separate world truth, character beliefs, reader reveal, relationship history and event consequence. Evidence extraction must be resumable/idempotent, with no automatic canon promotion.

**P1 — establish golden continuity questions.** Create at least 50 human-authored Book 1–80 questions covering first appearance, changes of knowledge, conflicting claims, chronology, motives and negative cases. Each answer must cite exact source and be evaluated by two independent knowledgeable reviewers. Evaluate false positives, evidence leakage, abstention and time-to-answer. Do not ingest external answer keys as authoritative without source review.

**P1 — fix local model reliability.** The requested reviewer timed out on a small metric-only input, even with a 3B model. Implement model health, queue control, constrained streaming, timeout/cancellation, supported fallback and progress/error UI. Do not attempt 80-book context stuffing; use retrieval and staged synthesis.

**P1 — preserve publication data quality.** Current volume title is derived from filename; capture and display EPUB metadata and author/editor credits separately, preserving original byte snapshots and metadata conflicts. Support clear first-run import summary, duplicate/edition choices and progress with rollback.

**P2 — polish the search and learning experience.** Reduce oversized headers and extra navigation. Show a compact book-number selector, explicit source and spoiler boundaries, chapter/scene citation jump, meaningful related-source grouping and a persistent query/reading-position bookmark.

**P1 — adversarial ZIP and recovery tests.** Validate nested EPUB decompression budgets, entry counts, symlinks, encrypted ZIP entries, zip-slip paths, partial failure, simultaneous imports, index corruptions and restoration from backup. Keep immutable originals separate from derived indexes.

## Hands-on author acceptance walkthrough on the Windows test computer

1. Open **http://127.0.0.1:5173/** from the Windows computer; select the existing synthetic project if prompted.
2. Choose **Series**, then select **The Destroyer - 80-Book Continuity Lab**.
3. Under **Explore**, use **Find the evidence, across every book**. Search **Remo**, **Chiun**, **Sinanju**, **Smith**, or **CURE**. Confirm book-labeled cited result cards and open an original source.
4. Drag **Only show evidence up to** to **Book 20**. Search again; returned cards must be from Books 1–20, even though 80 books remain imported.
5. Switch to **Book 1**; repeat. Run a nonsense search; expect zero and an honest no-evidence message.
6. Open **Character minds** and **Verify → Review canon**. Expect **zero approved canon facts**. Ember should abstain from confident story-knowledge answers rather than inventing them.
7. Use **Discover** only to inspect candidates; approve none until their quotations and chronology have been personally checked.
8. Under **Library**, search volumes by book number or title and inspect imported immutable source metadata. Do **not** re-import the same ZIP into this already populated vault (duplicate positions are blocked).
9. Exercise a known multi-book continuity question from your own knowledge of the series, then record **expected answer + exact supporting volume/scene**. If Ember cannot provide independently verified citations, count that test as **not passed**.

## Engineering acceptance links

- `docs/reviews/destroyer-80-book-import-evidence.json` — local import metadata, no prose
- `docs/reviews/destroyer-80-book-search-benchmark.json` — timed query metrics, no prose
- `docs/reviews/destroyer-series-agent-probe.json` — privacy-safe 80-source and cutoff QA
- `backend/tests/test_series_bulk_import.py` — synthetic import isolation/validation
- `backend/tests/test_series_evidence_search.py` — exact source coordinates and spoiler boundaries
- `scripts/destroyer_browser_audit.mjs` — actual visual interaction capture; screenshots remain private under `.ux-audit/destroyer-library`

**Release decision:** Human continuity exploration **READY**. Deep series knowledge **NOT READY / no 5/5 approval**. The books remain available only on the authorized PC; the repository contains code, synthetic fixtures and numeric testing metadata only.
