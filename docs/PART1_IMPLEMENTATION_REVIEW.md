# Part 1 implementation review — Story Observatory / Living Story Intelligence

**Build:** `feature/part-1-story-observatory` · draft PR #131 · 12 November 2026

## What has been implemented

Part 1 is now a real integrated UI and local backend slice, not a conceptual prototype.

### 1. Universe constellation
- Professional visual starfield with native, keyboard-selectable entity nodes; their connections are drawn only when the approved fact store contains explicit linked assertions.
- Search by entity name, alias or kind. Color and symbols identify people, places, artifacts, factions, events and rules; graph selection is exposed beyond color.
- Contextual inspector displays applicable cited facts, world truth vs character belief vs reader knowledge, and source excerpt; links open the existing Canon Graph with the correct source selected.
- Facts cannot become established without explicit author review. Approved/proposed state is always labeled and proposed assertions are filtered separately.
- A visible story time machine changes the selected book and reissues a spoiler-scoped data request rather than trusting stale client state.

### 2. Character minds
- Professional character focus gallery and psychological facet cards for goals, fears, secrets, voice, and identity/values.
- Each non-empty facet is sourced to an author-approved assertion and contains the evidence quote/volume. Unestablished traits are left blank instead of guessed.
- Selecting a cast member keeps the author in the psychology lens; an explicit link opens the full character node in the Universe view.

### 3. Plot threads
- Interactive setup/payoff rail grounded in approved `foreshadows`, `setup_for`, `reveals`, `resolves` etc. predicates.
- Shows unresolved threads, resolution events, and payoffs for which the available source-backed fact graph has no prior setup.
- Source quotations and book events are displayed at each point. No unsupported inferred plot events are inserted.

### 4. Story history
- A book-ordered evidence chronicle shows approved changes in story knowledge, with distinct world / belief / reader scopes.
- Individual events navigate back to the entity inspector; book-time selection is consistent across lenses.

### 5. Local Model Lab
- Three repeatable synthetic scene prompts designed to test character knowledge boundaries, setup/payoff, and scene aftermath.
- User-initiated benchmark only; results preserve word counts, passage structure, required named elements, forbidden phrase signals and repeated n-gram warnings.
- Uses installed Ollama models through an HTTP loopback-only endpoint. Known cloud/remote aliases are rejected.
- Asynchronous local job status, progress per scenario, and results are saved under the local Series Vault.
- No author manuscript is sent to the model lab; the only prompts used by the benchmark are synthetic.

### 6. Unified series story-state service
- `GET /api/series/{id}/story-state?book={ordinal}&sequence={scene_index}` assembles facts, author-approved evidence, separate character belief and reader reveal perspectives, source-aware entity profiles, explicit relationship edges, threads and conflicting assertion warnings.
- Pending proposals remain separate and are never silently elevated to canon.
- Linked source snapshots are checked for staleness. A changed manuscript is surfaced for author review, never silently used to invalidate a checksum-backed source quotation.
- Existing series backup, sources, temporal queries, Canon Graph, Continuity Guardian and Consequence Map remain available alongside the Observatory.

## Intended author flow
1. Series → select or create a series in the private Series Vault.
2. Add author-owned source volumes. Source snapshots remain immutable.
3. Open Story Observatory → visually explore the Universe, switch book/time, select character or artifact.
4. Open a fact → inspect its exact source quote and where it is applicable; follow the citation to Canon Graph.
5. Explore Character Minds for sourced motivations, fears and voice, Plot Threads for setup/payoff, or Story History for reveal ordering.
6. Go to Canon Graph to propose, explicitly approve, or reject author-considered facts. The Observatory refreshes to show the new approved state.
7. Review contradiction or stale source warnings through existing Canon Graph / Series Vault.
8. Optionally open Model Lab and start a fully local synthetic model evaluation. Return to the manuscript; no text is automatically inserted or canonized.

## Verification completed
- Frontend: `npm run build` passed after all integration changes.
- Focused backend: `python -m pytest -q tests/test_series_story_state.py tests/test_story_generation_eval.py tests/test_series_canon.py tests/test_series_professional.py` passed **23 tests** after introducing the stale-source check.
- Browser: synthetic-only Chrome CDP interactive visual test passed at **1440px, 900px and 390px**; no measured page-level horizontal overflow, and no story-state endpoint errors.
- Five lenses and book navigation exercised with the synthetic three-volume series *The Astral Lanterns*, ten named entities, 22 accepted facts at Book 3 and one pending proposal.
- Source of truth was created in isolated `part1-demo-data`, not the author's manuscripts; screenshot captures are synthetic and safe to publish.
- Model Lab model discovery was checked against the local Ollama registry and displayed locally installed models once the request completed. Cloud-prefixed aliases are excluded.

## Known limitations / unpassed release gates
- Live end-to-end `llama3.2:3b` model generation **timed out after the configured 300s** on the workstation; this is not a successful real-model quality benchmark. The harness and local-only API path are implemented and tested with mocks, but real model scores and latency remain unverified.
- Character facets and plot threads currently project from author-approved, explicit source-linked predicates. The system does **not** automatically understand the entire imported novel or reconcile every edited paragraph to new canon. It flags stale source snapshots and leaves author-controlled re-approval to the Canon Graph. Full-book automatic extraction is a separate substantial release gate.
- Spatial travel, character psychology evolution beyond cited facts, automatic narration/symbolic interpretation, and semantic entity alignment over a 12-book career corpus have not been proven by the focused tests.
- Mobile width and desktop UI were smoke-tested, not certified to WCAG; full NVDA/VoiceOver, high zoom, reduced-motion device, keyboard-only path and performance across thousands of entities remain future release gates.
- The original app has known Vite chunk-size and Harper browser externalization warnings; these did not cause the local build to fail.
- **This is a draft PR and not merged into `main`.** Treat it as an author review build, not a public release.

## Screenshots (all synthetic app captures)
The PNGs under `docs/screenshots/part1-synthetic/` were captured from the running application, not AI-generated mockups. Recommended reviews:
- [Universe desktop](screenshots/part1-synthetic/01-universe-1440.png)
- [Universe graph detail](screenshots/part1-synthetic/16-graph-detail.png)
- [Character Minds](screenshots/part1-synthetic/02-character-minds-1440.png)
- [Psychology evidence cards](screenshots/part1-synthetic/17-psychology-detail.png)
- [Plot Threads](screenshots/part1-synthetic/03-plot-threads-1440.png)
- [Plot rail details](screenshots/part1-synthetic/18-threads-detail.png)
- [Story History](screenshots/part1-synthetic/04-history-1440.png)
- [Model Lab](screenshots/part1-synthetic/04b-model-lab-1440.png)
- [Model run controls](screenshots/part1-synthetic/20-model-lab-controls.png)
- [Responsive mobile](screenshots/part1-synthetic/07-mobile-390.png)
