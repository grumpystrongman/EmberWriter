# Stage 2 — Chunk 9: Reproducible Literary Evaluation Gate

Date: 2026-11-14
Status: Implemented as a **synthetic local diagnostic**. The production algorithm is explicitly *not certified for semantic scene, POV, or character-knowledge inference*.

## Product problem

In Chunk 8 the author can navigate source-exact chapter-based reading windows and manually approve or reject scene interpretations. Those windows are built using verified EPUB chapter formatting, typographic separators, and length caps. A formatting break does not establish a fictional scene break. No model has shown reliable semantic scene detection, viewpoint classification, or cross-book knowledge tracking.

We need an independent, reproducible standard before allowing automated narrative intelligence. The first baseline is intentionally challenging rather than fitted to the current segmenter.

## Delivered

- `backend/app/series_scene_gold.py`: 12 standalone original synthetic-fiction passages with predeclared ground-truth boundary, viewpoint category, character knowledge label, and interpretation note. Fixtures include explicit and implicit scene changes, first person, omniscient switches, dreams, flashbacks, an unreliable narrator/claim, later-book revelations, decorative dividers and long unbroken scenes. Each fixture carries stable, hashed dataset metadata.
- Scores every **computed navigation break** against the fixture's declared actual scene boundary. Reports true positives, false positives, false negatives, true negatives, precision, recall and F1. Extra length-driven divisions and falsely meaningful decorative symbols count as errors. The meter does *not* convert reading-window proximity into narrative understanding.
- Viewpoint and knowledge scores track evidence coverage independently. The current system explicitly abstains rather than pretending it predicted narrator type, motives, truthfulness, or character beliefs.
- `GET /api/series/{series_id}/scene-evaluation?book=N`: checks series isolation, returns only the synthetic diagnostic, and adds read-only counts from that series' existing author decision ledger. It never calls an external/local model, shares manuscript text, or writes any canon assertions. The fixture evaluation does not use a series' unpublished manuscript.
- `StorySceneEvaluation.tsx`: an expandable **compact ReviewQueue** under **Series → Explore → Story History → Chapter and Passage Explorer → Literary interpretation quality gate**. Displays a concise metric strip, blocked-certification warning, and each original synthetic case with its reference excerpt, predeclared expected break and POV, and observed navigation splits. Author-reviewed source passages remain a distinct ledger.

## Baseline — November 14, 2026

| Measure | Observed |
|---|---:|
| Predeclared synthetic cases | 12 |
| True positives (correctly aligned break) | 4 |
| False positives (unwarranted navigation divisions) | 2 |
| False negatives (missed genuine scene changes) | 4 |
| True negatives (correctly no scene division) | 2 |
| Precision | 66.67% |
| Recall | 50.00% |
| F1 | 57.14% |
| POV prediction coverage | 0 / 12 |
| Supported character-knowledge prediction coverage | 0 / 5 known fixture cases |
| Automatic semantic scene certification | **BLOCKED** |

Examples of specific problems: a decorative `***` produced an undeserved split; a chapter-length continuation produced a length-driven split; plain-paragraph time/place shifts and flashbacks did not trigger a new scene. This is *expected evidence* of the distinction between layout and semantic literary intelligence, not a bug to hide by manipulating the fixtures.

There is **no generalization claim** from 12 synthetic examples to real novels. Any future model/heuristic must be evaluated independently on unseen and human-confirmed excerpts with abstention criteria, source citations, and anti-leakage constraints. Updating the fixture bank changes its SHA-256 fingerprint and must be treated as a benchmark revision.

## Validation

- Six new tests verify fixture diversity, fixed gold labels, strict gate blocking even for a deliberately easy perfect case, all extraneous boundary penalties, deterministic SHA-256, read-only API/series isolation, and that author-confirmed scene review records never get silently treated as gold.
- Full Series backend regression suite: **192 passed**, with one expected warning from the synthetic duplicate-mimetype attack test; four release-scorecard tests passed. Python Ruff checks and TypeScript/Vite production build passed.
- Actual API calls on Destroyer Book 1 and Book 80 returned the same 12 synthetic cases, blocked status, no external model calls and no private source transmitted; author scene reviews remain unmodified.
- Browser smoke opens the real Book 80 scene explorer, verifies the existing 40-row local source research queue and full source text, then displays 12 compact gold cases, 67%/50%/57% metrics and the visible blocked certification. Previous 80-book metadata, Character Minds, dialogue, approved 4-book fixture, recovery tools, and batch extraction remain accessible.
- Source manuscripts, immutable EPUB indexes, original EPUB files, and approved canon records are untouched; no private literary text enters Git.

## Outstanding milestones

1. Recruit actual author-reviewed gold annotations across multiple real chapters, labels and books, clearly separated from inferred scene reviews. Their data must remain local and author-controlled.
2. Build independent candidate segmentation and viewpoint hypotheses and score against held-out author-reviewed data, not just authored synthetic fixtures.
3. Extend the evaluation to knowledge-state transitions, revelation timing, negative evidence and cross-volume contradictions. No prediction should update canon without author review.
4. Continue improving dense list views with grounded author feedback rather than reverting to full-width card stacks.

**This diagnostic is a release blocker, not a release pass.**
