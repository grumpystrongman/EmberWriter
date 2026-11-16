# Stage 2 — Chunk 3: Source Structure and Honest Local-Model Proof

**Review date:** November 13, 2026
**Branch:** `feature/stage2-chunk3-scene-model-probe`
**Release decision:** **Reviewable engineering checkpoint; no 5/5 certification or stable release.**

## Implementation delivered

### 1. Structural source navigator
- Added a **read-only source section index** behind `GET /api/series/{series_id}/sources/{source_id}/sections`. It recognizes only explicit line-anchored Markdown headings, Chapter/Part/Section markers, Prologue, Epilogue and Interlude, with exact immutable character offsets, source hash, character counts and conservative source-identification confidence.
- In Series → Verify → Review canon → Source evidence, authors can expand **Jump to a source chapter or section**, filter structural headings and jump directly to the original position. Changing source position clears the previously staged quote, preventing stale-quote misapplication.
- **Critically, the app never equates chapter headings or source offsets with in-world chronological order.** If imported source text has no verified headings, it displays a single *Whole source (no reliable chapter headings detected)* instead of fictional or invented chapter numbers.
- Tested genuine Series Vault isolation; no source text is returned by the index API; all passages remain on the owner's PC.

### 2. Synthetic local-model inference proof
- The previous `local-model-readiness` API only confirmed the Ollama service was accessible. Added a separate explicitly initiated `POST /api/series/{series_id}/local-model-probe` and a button in **Knowledge Lab → Local AI readiness**.
- The probe sends **only invented test text** (`Mira protects Rowan.`) to an installed loopback Ollama model and requires exact JSON with the correct protected person and source quotation. It measures wall-clock latency, reports `passed`, `incorrect`, `timed_out`, or `unavailable` accurately, and enforces a 30-second timeout. The response returns no generated prose.
- Model installation is **not** treated as model accuracy. No real books, excerpt or manuscript content enters the probe. The author must click to run it.

## Actual local workstation findings

| Installed local model | Exact answer | Observed latency | Result |
| --- | --- | ---: | --- |
| `llama3.2:3b` | Failed strict expected answer+quote | **9,510.7 ms** | **incorrect** |
| `lfm2.5:latest` | No answer in deadline | **30,415.8 ms** | **timed_out** |
| `qwen3.5:4b` | No answer in deadline | **30,514.0 ms** | **timed_out** |

These were individual, real synthetic-only requests on the connected Windows computer (see `2026-11-13-stage2-chunk3-local-model-probe.json` and `2026-11-13-stage2-chunk3-local-model-comparison.json`). **Zero of three models passed the exact tiny inference test.** Therefore local-model reliability must remain an explicit blocker on the 38-item master scorecard. Do not advertise this as 5/5. The observed model failure could reflect load, startup, prompt adherence or hardware constraints; the current measurements do not isolate which.

**Private 80-book source-structure reality check:** structural indexes were requested for Destroyer Books **1, 20, 40, 60 and 80**. All five returned one unsegmented source, **zero literal headings** and no fabricated chronology; measured responses **13, 43, 34, 32 and 31 ms** respectively. The source importer currently flattens EPUB structure, leaving inadequate reliable headings in these examples. **Next fix must preserve original EPUB spine/ToC/nav and chapter boundaries during import**, with edition-aware mapping to the exact text snapshot, rather than guessing them from prose. The user-provided ZIP is still on the Windows PC; it must never be added to Git or automatically reimported over existing volumes.

### 3. Author-review UX and synthetic browser proof
- Added a compact source-section search/navigator and an opt-in local inference check in the existing research UI.
- Re-ran a real three-book **temporary synthetic fiction** journey: seven approved test claims, book 1/3 future knowledge boundaries, setup→payoff, exact quote/source drilldown, section jump and mobile/tablet/desktop layout checks, with zero document-level horizontal overflow at 390/900/1440px. Synthetic fixture was deleted after testing.
- Actual synthetic screenshots:
  - [Desktop source-backed knowledge](assets/2026-11-13-stage2-chunk3/01-approved-world-truth-desktop.png)
  - [Book 1 without future revelations](assets/2026-11-13-stage2-chunk3/02-book1-no-future-spoilers.png)
  - [Plot promise and payoff at Book 3](assets/2026-11-13-stage2-chunk3/04-setup-and-payoff.png)
  - [390px mobile Knowledge Lab](assets/2026-11-13-stage2-chunk3/05-mobile-knowledge-lab.png)
  - [Section navigator linked to exact source](assets/2026-11-13-stage2-chunk3/07-source-chapter-navigator.png)

## Verification and acceptance

- **63 targeted tests passed** across model probe, section detection, resumable extraction and synthetic 50-claim knowledge regression; Ruff checks passed for changed Python code; TypeScript/Vite production build passed.
- **7 more** targeted tests specifically covered model probe and source navigation. All are synthetic, never the imported copyrighted book text.
- Real Chromium walkthrough passed the selected seven-claim synthetic scenario; metadata `2026-11-13-stage2-chunk3-browser-evidence.json`.
- **Full backend regression VERIFIED:** **756 passed, 6 skipped, 0 failures**, with one expected Python ZIP duplicate-name warning from the malicious EPUB test; completed in **244.17 seconds**. Exact local log: `.ux-audit/stage2-private/chunk3-full-regression.txt` (ignored from Git).

## Expert novelist / senior UX reviewer findings

**A. Critical: data quality.** The real 80-book sample has no identifiable chapter boundaries after text import. This is a source-ingestion preservation problem, not a prompt-engineering problem. Do not create phantom scene order.

**B. Critical: model reliability.** Three real local models had zero strict passes on a tiny invented-text question. Do not run automatic deep knowledge extraction of all 80 books or claim 5/5 until inference is reliable, model readiness is truthful, and the user can see progress, limits, errors and exact evidence.

**C. Important: literary cognition.** Source coordinates and explicit author-approved facts are valuable but do not constitute causal understanding of characters. Build evidence-linked scene/events, knowledge boundaries, conflicting beliefs, relationship changes, motives and author-graded questions rather than purely lexical name counts.

**D. Good progress: UX.** The tool presents source evidence and context with one-click navigation and a clear distinction between detection and interpretation. Continue reducing nested navigation and test actual screen readers, keyboard use, 200/400% zoom and 250K–500K-word responsiveness.

## Remaining path before Stage 2 earns 5/5

1. **Preserve EPUB structure**: spine, ToC, headings and chapter-to-snapshot offsets; support safe private reindex of the current 80-book archive with no overwrite and author preview/confirmation.
2. **Fix model execution quality/throughput** with measured concurrency limits, startup-vs-inference diagnostics, bounded streaming, cancellation and realistic per-model timeouts.
3. **Build source-grounded scene/event proposals** with citeable evidence and author approval; distinguish structural position vs in-world temporal fact.
4. **Run at least 50 independently author-reviewed cross-book questions** against the private Destroyer reference corpus, including negative answers and book cutoff; score accuracy, leakage, hallucinations, provenance and user experience.
5. Expert agent review must be compared with real authors' judgment, not self-awarded scores. No 5/5 signoff without proof.

**The existing 38-item release gate remains locked.** All user-provided copyrighted book texts remain private on the PC. Repository artifacts contain only synthetic screenshots, code and numeric measurements.
