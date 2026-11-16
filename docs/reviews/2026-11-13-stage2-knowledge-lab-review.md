# Stage 2 — Deep Story Intelligence / Author-Reviewer Acceptance

**Date:** 2026-11-13
**Branch:** `feature/stage-2-story-intelligence` (based on Stage 1 `feature/scorecard-release-gates`).
**Verdict:** **Stage 2 implementation candidate, not 5/5 certified. No production release.**

## What is genuinely built

1. A source-backed **Knowledge Lab** in Series → Verify. Its author-operable book boundary and scene sequence, character subject, other participant, and belief-holder selectors present approved evidence in nine lenses: world truth, character belief, reader knowledge, relationship assertions, psychology facets, causal statements, plot setups/payoffs, changed facts, and possible contradictions. On phones only book/subject and one lens are immediately visible; advanced filters are disclosed rather than shown as a giant form.
2. **Every displayed assertion is linked to immutable original evidence**, including book, exact source character coordinate, quoted passage and SHA-256 source fingerprint. An author can open it in the existing Canon inspector. The surrounding source remains local.
3. **Explicit author-approval boundary:** source evidence search can stage exact text into a draft claim, but this does not save or approve an assertion. The author must choose the fact and save the proposal, then approve the proposal separately.
4. **Point-in-time knowledge:** approved world truth, character belief and reader reveal remain separate. Future-book or future-scene claims never appear at an earlier selected position. A book/scene chronology is *author-specified* and does not pretend that raw EPUB character offset equals in-world story time.
5. **Conservative change and contradiction detection:** genuine changes with nonoverlapping intervals are treated as recorded changes; coexisting goals, beliefs and relationships are *not* automatically contradictions. Overlapping conflicting claims are flagged only for explicitly single-valued predicates (e.g., one location), and always require author interpretation. These safeguards were applied consistently to the existing Story State and Canon timeline read models.
6. **Evidence-linked plot promise lifecycle:** explicit approved setup, promise, foreshadowing, reveal and payoff predicates appear in chronological chains. The application does not infer that a payoff is artistically earned.
7. **Local model readiness:** a bounded 3-second, loopback-only Ollama /api/tags health probe detects installed local models without sending source text. Service availability is clearly distinguished from successful long-form model inference. Existing author-selected optional AI suggestion support remains separate.

## Measured acceptance

- **50 synthetic golden book/character questions**, five book positions × ten subjects, with expected specific approved answer and exact source citation, including future-book exclusion. This is machine-generated regression, **not** an independent or copyrighted-corpus literary gold benchmark.
- Additional synthetic facts test source/quote correctness, pending vs approved, as-of book and scene cutoffs, character beliefs separate from reader reveals, literal causal links, setup/payoff lifecycle, false contradiction avoidance, subject+counterpart relationship matching and cross-series isolation.
- **Real synthetic Chromium walkthrough**: temporary local *Glass Horizon* three-volume series, three characters/entities, seven authored-and-approved assertions. Captured six actual app screenshots and checked:
  - Book 1 shows three approved facts and does not expose later-book content;
  - Book 3 shows the complete seven-fact set including one reader reveal;
  - Plot promise is **open in Book 1**, **resolved by explicit approved payoff in Book 3**;
  - Source button opens the correct quoted passage;
  - 390px phone, 900px tablet and 1440px desktop have no measured document or Knowledge Lab horizontal overflow;
  - Temporary fixture removed after use; author's manuscript never modified.
- **Private Destroyer series Chromium walkthrough**: all **80 reference books** remain indexed; as-of Book 20 and whole series return **zero approved facts** (correct abstention), no invented contradictions; exact **380-character** source passage staged for review, not saved; screenshots containing user-provided copyrighted excerpts are retained **only on authorized Windows PC** under ignored `.ux-audit/stage2-private`.
- The independent local model reviewer that previously timed out has **not** been cured by a quick health probe. This is a still-open Stage 2 release blocker.
- **Full backend regression: 743 passed, 6 skipped, 1 warning, 0 failed** on this branch, tested on November 13, 2026 in 194.89 seconds. The one warning comes from deliberately creating a duplicate EPUB mimetype for adversarial importer testing. Full log remains locally in ignored `.ux-audit/stage2-private/full-regression.txt`.

### Actual synthetic app screenshots

- [Approved world truth / source cards, desktop](assets/2026-11-13-stage2-synthetic/01-approved-world-truth-desktop.png)
- [Book 1 future-proof boundary](assets/2026-11-13-stage2-synthetic/02-book1-no-future-spoilers.png)
- [Book 1 promise without future payoff](assets/2026-11-13-stage2-synthetic/03-setup-no-future-payoff.png)
- [Book 3 promise + source-backed payoff](assets/2026-11-13-stage2-synthetic/04-setup-and-payoff.png)
- [Refined author-first mobile Knowledge Lab](assets/2026-11-13-stage2-synthetic/05-mobile-knowledge-lab.png)
- [Tablet Knowledge Lab](assets/2026-11-13-stage2-synthetic/06-tablet-knowledge-lab.png)

The original mobile hero in an earlier run was unreadable because the title shared width with a large statistic. That defect was **observed and corrected**, with a fresh 390px screenshot. Advanced filters were also moved behind a disclosure, and mobile lenses replaced with a labeled select. The first meaningful book/subject controls and active lens are now visible on the 390px first screen. This is a verified fix at the measured width, not full WCAG certification.

## Independent expert-author rubric (provisional; no unearned 5)

| Area | Assessment | Gaps before 5/5 |
| --- | --- | --- |
| Source-linked research | 4/5 | Full 80-book human-reviewed answer set, edition-aware citation reconciliation, interrupted data and multi-window editing |
| World / belief / reader separation | 4/5 | 50+ independently reviewed literary questions, author-validated scene order and events in real prose |
| Character psychology | 2/5 | Motives, fears and wounds are structured and accurately cited **when author-supplied**, but have not been reliably extracted or independently judged from novels |
| Relationship evolution | 2/5 | Timeline and source links work; emotional transitions and why trust changes remain author-proposed, not independently reasoned |
| Plot causality | 2/5 | Explicit setups/payoffs and cited causal predicates; no evidence that the system can distinguish real dramatic causality from narrative mentions |
| Continuity reasoning | 3/5 | Conservative single-valued conflicts and abstentions; no adversarial real-novel precision/recall or author-reviewed outcomes |
| UI visual maturity | 4/5 | Professional source cards, readable reflow and progressive disclosure; no NVDA and zoom/multiday field-study |
| Local model reliability | Unrated | Previous Ollama semantic reviewer timed out; bounded /api/tags readiness is only transport health, not inference proof |
| Security and source privacy | 4/5 | Loopback test and no source text in Git, explicit approval; still need adversarial cross-process backup and wider threat review |
| Overall Stage 2 | **NOT CERTIFIED** | Do not upgrade SER/CRAFT/UX gates in master 38 until evidence and independent human approval exist |

These are the author's and application's current test conclusions, **not an independent external novelist's signoff**. A custom UX-reviewer agent can audit against this rubric, but cannot confer independent real-world human literary validation.

## What would materially achieve 5/5 in Stage 2

1. **Scene segmentation and evidence graph:** identify chapter/scene boundaries in EPUB and manuscript text with exact offsets and scene-specific chronology; avoid assuming source position equals timeline.
2. **Bounded, resumable, author-reviewed semantic extraction:** small private source windows + local model queue, cancel/retry/timeouts; strict quote/offset verification; idempotent proposals; no approval without author review.
3. **Genuine character development and relationship causality:** represent goals, secrets, false beliefs, trust changes and their causal events; distinguish character belief/world/reader knowledge at scene scale. Human review is required to validate nonliteral psychological interpretation.
4. **80-book human-curated benchmark:** at least 50 cross-volume Destroyer questions with evidence and negative controls, independently labeled and graded. The current 50 synthetic questions only prove deterministic retrieval mechanics.
5. **Local model completion and latency:** model readiness is not enough; validate actual output, streaming, context bounds, interruption, repetition and response times on the user's computer.
6. **Novel-sized and accessibility certification:** performance with thousands of claims and multiple editions; independently test keyboard, screen reader and 200/400% zoom. Keep release gate locked.

## Author walkthrough on connected PC

Open **http://127.0.0.1:5173/** → Series → select *The Destroyer - 80-Book Continuity Lab* → Verify → Knowledge Lab. Start at Book 20. Switch World truth / Character belief / Plot promises / Continuity alerts: with zero approved facts, each must explicitly say there is insufficient evidence, not invent anything. To create a real source-backed fact, search evidence, select a cited passage and click **Draft a source-backed claim**, select the subject and meaning, save as a proposed fact, then deliberately approve only after reviewing the exact quote. After approval the claim can appear in the Knowledge Lab only at appropriate temporal positions. Do not test approval with real novel text without choosing and verifying the claim yourself.

**Release decision: Stage 2 code is ready for review, but not a 5/5 literary knowledge system. The 38-gate master release lock remains enforced.**
