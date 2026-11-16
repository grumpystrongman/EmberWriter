# EmberWriter Release Lab — Unified 38-Gate Author Quality Build

**Audit date:** 2026-11-13. **Candidate branch:** `feature/scorecard-release-gates`. **Status: NOT RELEASE CERTIFIED.**

## What was built in this pass

1. **One integrated release scorecard, 38 independently measured author outcomes** across the five systems: Author experience (10), Story intelligence (10), Safety & infrastructure (5), Publishing & delivery (4), Professional author features (9). All ten UX/author-experience domains from the November 13 product audit and all ten Destroyer 80-book domains are covered; the additional 18 criteria capture manuscript, release and professional writing capabilities. No criterion can silently disappear from the catalog: `node scripts/verify_release_scorecard.mjs --catalog` enforces exact coverage and uniqueness.
2. **A mature, interactive Quality / Release Lab inside EmberWriter** under **More → Tools → Release Lab**. Visual score ring, five domain meters, real risk filter, all 38 expandable acceptance gates, author outcomes, proof requirements, current evidence, text search, copyable acceptance plan and responsive mobile layout. Scores are expressly provisional; zero independently signed-off 5/5.
3. **A real release certification blocker**, not a cosmetic counter. `node scripts/verify_release_scorecard.mjs --certify release/quality-evidence.json` rejects missing/incomplete/synthetic evidence, wrong commit SHA, missing or tampered hashed test results, missing independent author and expert attestations, duplicate or incomplete gates. GitHub workflow `.github/workflows/certified-release.yml` checks on release tags. It **fails by default**, intentionally, until every gate has real human-verified proof. The exact GitHub tag workflow is a CI status gate; protecting/deploying tags also requires repository policy and permissions.
4. **Safer source import for actual novels and 80-book archives**: shared EPUB zip preflight rejects unsafe internal paths, symlinks, encryption, too many inner entries, oversized individual XHTML content, excessive expanded size and suspicious compression ratio, before `ebooklib` touches document XML. Validation applies to both single-volume and bulk imports. Existing local 80-EPUB corpus passed all new preflights in roughly 0.03 seconds. Adversarial tests created synthetic nested EPUB bombs and confirmed rejection without mutating the Series Vault. This is preflight, **not yet isolated-process decompression, OS quota protection or complete malicious document security certification**.
5. **Character Evidence Atlas in Series → Explore**: choose Remo, Chiun or Smith and inspect how often names appear in immutable source text **across all 80 books**, with an interactive miniature bar sequence, book selection and a direct cited source-filtered result workflow. The whole visualization obeys the reading-position cutoff and keeps book text local; the desktop and phone browser audits verify real operation. This represents **source research**, not emotional understanding or canon. The 80-book pilot found **13,182 matching text windows for Remo**, with **3,170 through Book 20**, all confined to allowed volumes; overlapping windows can be counted more than once. Exact-source citation navigation is preserved. No character motives or story events were automatically approved.

## First-hand browser proof (only synthetic content committed)

- [Release Lab, 1440px desktop](assets/2026-11-13-release-lab/01-desktop-overview.png)
- [Interactive story intelligence filter](assets/2026-11-13-release-lab/02-story-depth-desktop.png)
- [Expandable acceptance evidence inspector](assets/2026-11-13-release-lab/03-proof-inspector.png)
- [Live P0 release-blocker filter](assets/2026-11-13-release-lab/04-release-blockers.png)
- [Release Lab, 390px mobile](assets/2026-11-13-release-lab/05-phone-overview.png)
- [Craft domain, 390px mobile](assets/2026-11-13-release-lab/06-phone-craft.png)

The real 80-book character atlas, book-20 citation results, and mobile charts contain copyrighted source titles or excerpts and therefore remain **only on the user's Windows PC** at `.ux-audit/destroyer-library/06-80-book-character-atlas.png` through `09-80-book-atlas-mobile.png`. The related metadata-only browser acceptance is stored at `docs/reviews/2026-11-13-character-atlas-test.json`, not book text.

## Repeatable proof

| Gate | Command | Current test evidence |
| --- | --- | --- |
| 38 mandatory gate definitions | `node scripts/verify_release_scorecard.mjs --catalog` | 38 unique entries; 5 groups; no provisional score of 5 |
| Full certification fail-closed | `node --test scripts/test_release_scorecard.mjs` | 4/4 tests including missing manifest, artificial AI-only review and incomplete coverage rejected |
| Release hold (intentional) | `node scripts/verify_release_scorecard.mjs --certify MISSING.json` | Exit 1, release held |
| Safety against malicious nested EPUB | `pytest backend/tests/test_series_bulk_import.py` | Oversized and traversal attempts rejected with unchanged vault |
| Source-trace and character timeline | `pytest backend/tests/test_series_evidence_search.py` | Source coordinates, as-of cutoff, alias/character isolation and HTTP endpoint |
| Complete 80-book character research | `node scripts/character_atlas_browser_audit.mjs` | Actual 80-book source-only bar atlas, Book 20 citations, 390px mobile no page overflow |
| Full UI release lab | `node scripts/release_lab_browser_audit.mjs` | 38 gates, domain filtering, P0 blocker filtering, proof inspection, 390/1440px layouts |
| Production frontend | `cd frontend && npm run build` | TypeScript/Vite production bundle compiles |

**Important:** These prove specific code functionality, not that the entire product reached 5/5. This deliverable intentionally **does not invent human reviewers, author usability trials, literary quality scores, Windows installer results or long-form Ollama success**.

## The blocker queue for actual 5/5

**P0 (release forbidden):** Proven global manuscript concurrency and crash recovery; reliable local full-scene generation and continuity quality measured against author-approved literary fixtures.

**P1 (release forbidden):** Independent keyboard/NVDA/WCAG audit; actual 20-author usability cohort; real novel-scale performance; fully versioned offline Ember help/wiki; complete source-based character belief and relationship evolution, provenance, narrative contradiction tests; selective scene draft → approved prose → canon; EPUBCheck, device/print proofing and Windows clean-machine/recovery.

**P2 (must close before "38/38"):** Beta reader feedback roundtrip, author customization, research citation system, writing cockpit polish, deep editorial quality and novel-specific documentation.

The 38 criteria are an auditable **acceptance contract** rather than 38 claims that those features have all been built. This pass demonstrably strengthens SER-01, SER-02, SER-03, ENG-05, UX-03/04 and quality governance; character knowledge/causality remains far below certification.

## Author testing

On the Windows test machine, open **http://127.0.0.1:5173**. In **Series**, select *The Destroyer - 80-Book Continuity Lab*, expand *Find the evidence*, then choose a character in **The Character Evidence Atlas** and click a bar. Choose **Inspect cited passages** to see exact sources in that book, limited by the selected reading position. In **More → Tools → Release Lab**, inspect the five quality domains and P0 blockers. No automatic canon approval, novel rewrite, public upload or cloud transfer occurs.

**Do not tag, publish or market this build as 5/5 until the complete audit pack and independent human author reviews exist.**
