# EmberWriter: expert author experience and 5/5 release-gate audit

**Review:** November 13, 2026 · **Branch:** `feature/ux-scorecard-hardening` · **HEAD at audit:** `074062d` plus explicitly uncommitted UX work · **Status:** **NOT READY FOR 5/5 SIGNOFF**.

**Grounding:** isolated synthetic project *The Ashen Coast — Synthetic Editorial Review*. Fresh Chromium captures at [2026-11-13-current-build](assets/2026-11-13-current-build/), DOM telemetry [JSON](2026-11-13-current-build-evidence.json), and current-run guided-interaction screenshots in [2026-11-12-scorecard-interactions](assets/2026-11-12-scorecard-interactions/). Each author task is scored only to the depth verified. Historical design mockups are not verification.

**Build checks:** TypeScript/Vite production build **passed**; backend regression **664 passed / 6 skipped / 0 failed** in 202 seconds; synthetic Chromium guided run **7/7 selected checks passed** (mobile navigation, More tray, offline help step progression, Series tabs, scene brief handoff). The backend suite does not certify UI usability or reliable long-form model output. The full accessibility, large-book performance, Windows installation and actual EPUB/retailer acceptance gates remain open.

## Current scorecard and evidence to earn five

| Dimension | Current provisional /5 | Evidence | Required for verified 5/5 |
| --- | ---: | --- | --- |
| Creative flow | **3** | [Write phone](assets/2026-11-13-current-build/write-mobile.png), [Plan phone](assets/2026-11-13-current-build/plan-mobile.png) | 10 novice + 10 experienced-author real task sessions; no losing chapter selection, seamless scene-to-prose-to-review-to-save, median time-to-first-words target set and met |
| Navigation / orientation | **3** | [Plan](assets/2026-11-13-current-build/plan-mobile.png), [Analyze](assets/2026-11-13-current-build/analyze-mobile.png) | A single edit/revise journey instead of competing tool hierarchies; author can tell which chapter/series and next action; target task success >=95% without coaching |
| Visual maturity | **4** | [Publish phone](assets/2026-11-13-current-build/publish-mobile.png), [Series desktop](assets/2026-11-13-current-build/series-desktop.png) | Editorial typography retained with reduced banner sizes, meaningful information visible in first viewport, polished loading/error/empty/confirmation states, tested visual regression at all breakpoints |
| Interactive depth | **3** | [Series](assets/2026-11-13-current-build/series-desktop.png); 7 passing synthetic interactions | Every diagram supports source-linked drilldown, scene selection, edit/undo/compare and completed effect; verify multi-step operations, not merely buttons and changing tabs |
| Cognitive load | **2** | [Editorial phone](assets/2026-11-13-current-build/editorial-mobile.png) | One apparent next action per tool, collapsible advanced panels, first manuscript signal above fold, task-flow click count and wrong-turn measurement with authors |
| Novelist usefulness | **3** | Chapter Pulse and Scene Director are real; scene handoff tested; semantic arc interpretation not established | Character contradictions, motivation and evolving relationship states evaluated against human-labeled scenes; accurate story-time knowledge, voice fidelity, true prose revisions, source receipts and series-scale cross-book results |
| Authorship / trust / reversibility | **4** | Publishing/revision backend tests, explicit scene handoff, export provenance; source states separated | Global version checking and atomic write locking, interrupted-build/recovery fault tests, every AI/canon/manuscript write reversible; no silent changes and provenance on every export |
| Accessibility / mobile | **2** | [Write phone](assets/2026-11-13-current-build/write-mobile.png), DOM reports unnamed/tiny controls; no measured horizontal overflow at 390/900/1440 | Automated axe + manual NVDA/VoiceOver + full keyboard + 200/400% zoom + high contrast/reduced motion + 44px major target audit; no severe WCAG 2.2 AA violations |
| Performance | **unrated** | The frontend built and pages rendered; NO large novel or interaction latency measurements | Repeatable 250K–500K word / 100+ scene tests; p95 interaction latency, save, project open, navigation, search, scene graph, local-model completion; crash/restore/load testing under realistic hardware |
| Contextual learning / Ember | **2** | [Guided help actual run](assets/2026-11-12-scorecard-interactions/07-ember-guided-step.png), five `preview` articles in `author-help.ts` | Versioned local complete wiki covering EVERY author task, actual screenshots and tested selectors, step verification (not merely manual checkbox), accessibility and undo; 10+ new-user scenarios pass on final frozen build |

**Rule:** A category is **5 only when its acceptance pack is linked to the exact shipping commit** (script, log, full screenshot sequence, fixtures, test results, device/platform, human signoff). All ten categories must pass, with no P0/P1 release blockers; 5 is not a cosmetic average. Performance is deliberately unrated rather than invented.

## Actual guided task walkthrough and condition

1. **Write chapter / resume:** [desktop](assets/2026-11-13-current-build/write-desktop.png), [phone](assets/2026-11-13-current-build/write-mobile.png) — **partial pass**: manuscript rendering and title correct; mobile formatting ribbon is several rows, technical source file path still shown; autosave/restore under failure not exercised in this run.
2. **Navigate to editing:** [Plan desktop](assets/2026-11-13-current-build/plan-desktop.png), [phone](assets/2026-11-13-current-build/plan-mobile.png) — **needs rework**: tool groups, additional Editorial overview/Prose Editor tabs and large Atelier header precede chapter evidence.
3. **Run critique / return to revision:** [Analyze desktop](assets/2026-11-13-current-build/analyze-desktop.png), [phone](assets/2026-11-13-current-build/analyze-mobile.png) — **partial pass**: separate Reader Perspectives screen and cross-link now exist; selective edit/approval/undo round-trip NOT re-run.
4. **Series character/knowledge/relationship:** [Series desktop](assets/2026-11-13-current-build/series-desktop.png), [phone](assets/2026-11-13-current-build/series-mobile.png) — **partial pass**: Explore/Direct/Verify/Library are real, but six Observatory sub-lenses plus source/entity complexity are still dense. Semantic psychological accuracy not evaluated.
5. **Scene storyboard to Writer:** [confirmation](assets/2026-11-12-scorecard-interactions/11-scene-writer-handoff-confirmation.png), [Studio result](assets/2026-11-12-scorecard-interactions/12-saved-scene-brief-in-writer.png) — **passed prompt handoff**: saved plan → explicit confirm → text present in Scene Writer without manuscript write. Actual real-model generation, author selection and manuscript integration NOT demonstrated.
6. **Publishing:** [desktop](assets/2026-11-13-current-build/publish-desktop.png), [phone](assets/2026-11-13-current-build/publish-mobile.png), [tablet](assets/2026-11-13-current-build/publish-tablet.png) — **partial pass**: actual milestone UI and import/export code present; generated files and retailer-accepted proofs not revalidated in this UI run.
7. **Ember help:** [library](assets/2026-11-12-scorecard-interactions/06-ember-offline-help.png), [guide](assets/2026-11-12-scorecard-interactions/07-ember-guided-step.png), [locate feedback](assets/2026-11-12-scorecard-interactions/08-ember-control-location.png) — **partial pass**: offline guide search, navigation and explicit self-reported progress. Only 5 articles, many target selectors unverified, instructions still labeled pre-release, and no automatic step-state validation.
8. **Responsive access:** [Write](assets/2026-11-13-current-build/write-mobile.png), [Analyze](assets/2026-11-13-current-build/analyze-mobile.png), [Publish](assets/2026-11-13-current-build/publish-mobile.png), [Series](assets/2026-11-13-current-build/series-mobile.png) — **partial pass**: bottom nav and 390px no overflow. Touch-target, full keyboard and assistive-technology audits needed.

## Release-blocking engineering gaps

- **P0 / DATA-001 — End-to-end write integrity:** global SQLite/project-file concurrency locks, compare-and-swap revisions, interrupted/partial writes, autosave racing undo, restore-on-migration, corruption injection and multi-window edits. Existing individual-safe-write tests are not sufficient to certify every pathway.
- **P0 / AI-001 — Inference quality + throughput:** live-model benchmark fixtures for 1K, 3K and full-scene generations; local Ollama availability and graceful failure; reliable stop/continue; fixed prompt source versions; zero-repeat and anatomical/spatial canon consistency checks. No proven latency distribution or literary acceptance signoff.
- **P1 / QA-001 — Missing complete frontend automation:** current `frontend/package.json` exposes a build and a visual smoke script, but no comprehensive Playwright/Vitest/axe regression pipeline for these workflows; current Chromium scripts cover a small subset. Add deterministic tests for *every* consequential author action and state.
- **P1 / REL-001 — Shipping reliability:** clean Win 10/11 installer/uninstall/update smoke checks, code signing, migrate forward/back in disposable projects, recovery after power loss, malware/AV false-positive validation, offline availability and accurate error messages.
- **P1 / HELP-001 — Wiki verification:** five preliminary guides are not a full release manual; enforce selector/step mapping, versioned screenshot links, start/end UI state, fallback and safe resume, first-time user trials.
- **P1 / A11Y-001 — Assistive access:** audit app-wide keyboard focus, hidden controls, semantics, contrast, 200/400% zoom and screen readers; DOM heuristics that counted unnamed and small controls require manual verification.

## Features to build or deepen before claiming excellent author usefulness

| Feature / depth | Current | Specific next interaction and definition of done | Priority |
| --- | --- | --- | --- |
| **Contextual manuscript inspector** | Multiple panels exist | From the prose cursor, open character/setting/plot context valid *at that scene's time*, cite exact passages, switch back without losing the caret | P1 |
| **Unified revision pipeline** | Plan Studio and Analyze separate | One chapter → flagged issue → source excerpt → suggested edit → side-by-side diff → selective accept → undo → history; all transitions real and reversible | P1 |
| **Character arc & relationship causality** | Useful facts/constellation and mentions | Author-editable beliefs/wounds/motivations, change-trigger timeline, evidence of the change, multi-participant state, secret-knowledge boundaries, contradiction handling | P1 |
| **Scene plan → actual draft** | Confirmed prompt handoff | Feed approved as-of-scene context into real generation, show alternative drafts and a line-level acceptance UI, apply only selected text without silent canon promotion | P1 |
| **Plot promises and payoff workbench** | Arc/promise tracking in Manuscript Pulse | Explicit promise → setup → reminder → payoff links, timeline and unresolved-at-final-chapter warnings with false-positive dismissal | P1 |
| **Voice fidelity evaluator** | Voiceprint/Dialogue Studio exists | Character-tagged quotes, repeatable voice challenge set, drift vs own baseline, safe suggestions preserving author voice, observed model results | P1 |
| **Versioned full Help Wiki** | 5 article preview Ember guide | Coverage inventory from actual final release, tests for each step and selector, screenshot-backed offline guidance, contextual help with success verification | P1 |
| **Manuscript-scale search and cross references** | Basic navigation/search exists | Global fuzzy/semantic *local* search across notes, chapters, characters and research with source filters and 100+ chapter scale performance | P1 |
| **Professional book proofing** | EPUB/DOCX/PDF, preview and provenance | EPUBCheck and accessibility checks, table of contents, split images, front/back matter, footnotes, scene breaks, long-chapter pagination, true eReader and print proofs | P1 |
| **Beta-reader/editor review round-trip** | Review comments exist | A private exportable feedback package with per-line location, issue status, import reconciliation, redaction and selective acceptance; no mandatory cloud | P2 |
| **Writer's progress and project cockpit** | Writing sprint exists | Per-project/session goals, time-bound planning, revision goals, chapter/scene milestones and resumption at exact last location; gamification optional | P2 |
| **Research source cabinet** | Reference capture + World exist | Offline indexed PDFs/web clips with attribution, quotes, fact/source confidence, manuscript links and exportable bibliography when needed | P2 |
| **Author customization and templates** | Genres and templates exist | Saved writing workspace layouts, keyboard shortcuts, non-disruptive palette/font/spacing and accessibility preferences per writer | P2 |

## Competitive relevance

Novelcrafter publicly exposes Codex progressions, scene-level context controls, prompt previews and version history; those are author expectations, not evidence that EmberWriter meets the same quality level. Scrivener emphasizes binder, snapshots, split research, writing targets and compile. Recent community discussions about Atticus/Vellum show why export fidelity, actionable failures and reliable restoration matter more than an attractive editor. Do not pursue collaboration, marketplace, cloud-first sync or mobile-native apps before the local manuscript workflow passes reliability gates.

## Order of execution / proof plan

1. **Stop scope creep; freeze the 5/5 acceptance rubric.** Add task fixtures, quality benchmarks and explicit owner-reviewed thresholds; collect a real author trial, not only scripted navigation.
2. **Protect the manuscript:** concurrency/atomicity/backup/migration/undo; fault injection + exact bytes before/after.
3. **Unify edit-review and reduce first-screen density** while preserving manuscript caret and navigation; validate desktop/mobile/keyboard.
4. **Finish scene and character intelligence:** board → live model → compare → selective apply → source/canon propagation, with real-world prose samples.
5. **Complete offline Ember wiki**, deterministic control IDs, release screenshots and step-state tests.
6. **Certification sprint:** large-project/local model throughput, axe + NVDA, clean Win installs, real EPUB/print proof, 20-author usability cohort; produce version-stamped signoff matrix.

**Verdict: ZERO dimensions are independently certified at 5/5 today.** The implementation is progressing, but passing a production build and 664 backend tests is not evidence that ten author-experience dimensions have reached a perfect score. Treat this report as the next release backlog and keep the stable-release tag blocked.
