# Four-part author experience roadmap — November 2026

## Product decision
The application should feel like a professional creative studio, **not a workflow of forms**. Each capability needs a visual way to explore the book, focused actions and inspectable source evidence. Do not introduce more top-level navigation for backend modules; keep existing Write / Plan / Series / Analyze / Publish pathways. All local source material stays in the local author project, and the author explicitly approves changes to canon or manuscripts.

## Part 1 — Story intelligence foundation and visual language
**Build now.**
- Unified Story State contract: connect manuscript, Series Vault, canonical evidence, book chronology, character knowledge, reader knowledge, relationships, locations and unresolved threads. Distinguish observed evidence, AI proposals and author approval. Preserve immutable citations and reversible choices.
- **Story Observatory**: visual, responsive entry surface into existing Series Vault state. Searchable entities, colored archetype cards, contextual fact inspector, book-position navigation, perspective filters, citation drilldown and explicit proposal approval/rejection.
- Generation quality harness: synthetic benchmark scenes, completion and repetition metrics, local-model routing, regression corpus, objective threshold tracking.
- Character psychology and individualized dialogue model: goals, wounds, voice, knowledge and emotional state.
- Plot thread/promise-payoff graph with manuscript anchors.
- Non-negotiable engineering: provenance, race-safe data fetching, deliberate privacy boundaries, keyboard use, screen-reader names, 390/900/1440 viewport checks, reduced motion and large-series load tests.

**Current PR scope (review build):** The Observatory now provides five interactive lenses (Universe, Character Minds, Plot Threads, Story History, Model Lab) backed by a unified read-only series-state API and explicitly approved manuscript evidence. A synthetic-only local model benchmark runner, progress, results, browser screenshots and 23 focused backend tests have been implemented. This is not full production acceptance: live Ollama evaluation timed out, automatic whole-book fact extraction and manuscript-to-canon reconciliation remain unimplemented, and accessibility/large-series stress gates remain unverified. See `docs/PART1_IMPLEMENTATION_REVIEW.md` for actual screenshots, test results and remaining work.

**Definition of done for Part 1:**
1. Import a synthetic multi-volume series and navigate its universe visually with no duplicate data entry.
2. Distinguish approved, proposed, rejected and absent canon; never silently elevate inference.
3. Scrub between books without future-book leakage; inspect supporting quotes and exact source positions.
4. Inspect a character's beliefs separately from objective truth and reader knowledge.
5. Author can approve or reject a proposal explicitly and immediately see consistent story views.
6. Generate representative scenes from local models and objectively report length, relevance, completion, continuity and repetition.
7. Synthetic browser tests validate accessibility, state transitions, privacy and layout at 390/900/1440 px.

## Part 2 — Character, relationship and scene director
- Character psychology cards with evolving arc visualization, private secrets, emotional injuries, goals, behavioral contradictions, spoken-voice signatures and knowledge as-of-book.
- Relationship constellation with selectable edges, trust/boundary history, tension, consent changes and group dynamics. Every change links back to manuscript scenes.
- Scene Architect 2.0: storyboard/beat cards, scene purpose, escalating obstacles, turning points, tension curve, location and participant state, direct author controls and aftermath ledger.
- Continuity Guardian across time, scene geography, objects, injuries, powers, knowledge and relationship state.
- Local visual scene direction, with optional author-controlled image references and media privacy.

**Design target:** draggable beat board and relationship network, not a long form. Prompts and advanced settings belong in collapsible inspector panels.

## Part 3 — Revision, criticism and professional author control
- Developmental Editor with narrative heatmap, stakes, pacing, character arc, promise/payoff coverage and citation-linked critique.
- Revision Workbench with split diff, accept/reject by change, snapshots, safe rollback and original voice fingerprint.
- Manuscript Health dashboard displaying ranked, actionable issues and before/after improvement, not arbitrary grades.
- Dialogue Coach, prose repetition analysis, meaningful scene variation and optional beta reader perspectives.
- Research workspace with fact provenance; advanced Atlas and travel consistency.
- Series-wide canon, cross-book memory and spoiler-safe reader knowledge as-of-point.

**Design target:** interactive manuscript heatmap, timeline, side-by-side revision canvas and clickable source anchors.

## Part 4 — Complete private author studio and distribution
- Professional export/compile: EPUB, DOCX, PDF, section presets, front/back matter and validation.
- Submission packages, privacy-respecting release and recoverability features.
- Multi-book project experience, library, templates, versioning and backups.
- Guided onboarding, accessibility audit, performance optimization, installer, local-model diagnostics and real author acceptance tests.
- Optional author workflow upgrades such as writing goals and beta-reader feedback, after core author success is reliable.

**Design target:** an elegant guided publishing desk with clear stage progress, previews and explicit release actions. No automatic publication or cloud manuscript transfer.

## UI acceptance criteria shared across all parts
- The first viewport answers: **where am I, what is the story telling me, and what can I do next?**
- Primary surfaces are spatial/visual: constellations, heatmaps, storyboard cards, relationship edges, chapter rivers, book covers and evidence panes.
- Every visual item is keyboard operable; status and selection are perceivable without color alone.
- A single context inspector handles detail instead of covering the workspace with forms.
- Zero fabricated backend data in production. Empty projects get actionable, beautiful empty states.
- Author approval for destructive or canonical changes, with immutable evidence and rollback paths.
- At most one major information surface visible initially; advanced settings are progressive.
- Test real novels/synthetic scale, 390px/900px/1440px, focus order, high contrast and reduced motion.

## Part 1 Observatory implementation notes
- Component: `frontend/src/StoryObservatory.tsx`
- Styles: `frontend/src/story-observatory.css`
- Integration: `frontend/src/SeriesDesk.tsx` (the Observatory opens by default and old tools remain accessible)
- Uses already loaded `/series/{id}`, `/entities`, `/assertions` records. Nothing new is uploaded to a remote service.
- Fact filtering is limited to the existing API's **book order** semantics. This view does not claim within-book chronology or a fully inferred relationship graph.
- Approval and rejection call the existing author review endpoint through SeriesDesk.
- **Not yet verified in a local browser/runtime** from this change; run `npm run build`, `npm run ux:visual`, focused series API tests, and a real keyboard walkthrough before merge.
