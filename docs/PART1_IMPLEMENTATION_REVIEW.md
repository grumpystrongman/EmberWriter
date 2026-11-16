# Part 1 rebuild — Living Story Intelligence

**Review date:** November 12, 2026  
**Repository:** EmberWriter · branch `feature/part-1-story-observatory` · draft PR #131  
**Release state:** Implemented and testable review build. **Not certified for public release** until remaining model/UX gates pass.

## Why it was rebuilt

The initial Part 1 was a thin facts viewer: it required nearly every important insight to have been manually approved before the UI became useful. The constellation looked like disconnected cards, it could clip on mobile, and the first full-viewport layout collapsed the graph behind the timeline. This revision fixes the visual defects and provides an evidence-to-canon author workflow rather than another form.

## The experience

### 1. Explore — the living Universe

- Enter the Observatory from Series Desk. Use **Enter immersive view** to expand beyond the normal app navigation into a focused, full-viewport exploration surface; Esc or **Return to Series Desk** exits safely.
- Select a node in the **interactive Story Constellation**. Characters, places, artifacts, and factions have distinct iconography; edges exist only when the accepted canon explicitly links the entities.
- A deterministic layout relaxation keeps visible nodes from overlapping. The synthetic 14-node graph passed an actual browser rectangle-collision test.
- The inspector shows the selected subject's applicable evidence, proposed vs approved status, reader/character/world perspective, original quote, exact characters, and a link to Canon Graph.
- Search by alias or name. The graph intentionally restricts visible items to a digestible set; the full series remains searchable.

### 2. Discover — go from manuscript to proposed canon

- **Discover** scans immutable, author-authorized source snapshots across the entire series or one selected book, using conservative literal sentence patterns. It does not contact any AI model automatically.
- Each lead includes a character, literal predicate, target, exact quotation, source title/path, original offsets and book of origin. Known reviewed assertions are excluded from results.
- Selecting a lead opens the dedicated evidence inspector, not an editor form. **Add to author review** creates a *proposed* assertion only. It is never approved automatically.
- The author then reviews that proposal in Canon Graph, explicitly approves or rejects it, and the Observatory reloads the accepted story state.
- **Deep Read** is an optional second stage: the author selects a local Ollama model to inspect the surrounding source passage for additional suggestions. The existing source-verifying API discards unverifiable quotations. Results remain unsaved until the author deliberately stages each suggestion.
- This is a useful whole-source discovery layer, **not** a claim that heuristic extraction semantically understands every sentence or can automatically reconcile all changed editions.

### 3. Understand — Character Minds, Plot Threads and Story History

- **Character Minds:** goals, fears, secrets, voice and values appear as evidence cards. Missing evidence is explicitly labeled unknown. Selecting another cast member updates the panel; clicking the full-history action returns to the graph.
- **Plot Threads:** published setup and payoff predicates establish rails with book and source evidence; reveals without established setup are not silently considered an earned payoff.
- **Story History:** author-accepted facts appear in book order, with separate world, reader and character belief scopes. Each item opens the relevant entity.
- **Story Time Machine:** select a book, then scrub within its available source/scene sequence points when available. The backend filters facts by book/sequence. A browser test verified facts disappearing when moving from the end of Book 4 to the beginning.
- Contradictory accepted facts and changed linked-manuscript snapshots surface explicit warnings.

### 4. Test — the local Model Lab

- Three synthetic writing scenarios exercise character knowledge, setup/payoff, and lasting consequence.
- Local installed Ollama models are selectable; known cloud/remote aliases are rejected. No manuscript content is included in benchmark prompts.
- Explicit author-triggered jobs save scenario progress, completion, length, required elements, forbidden phrase violations, repetitive five-word sequences and prose-format warnings.
- HTTP requests remain loopback-only, with explicit timeouts and helpful failure messages. Reports are diagnostic signals, not a fictional proof of literary quality.
- **Unpassed gate:** Direct real-model generation on the connected development machine timed out repeatedly, including a 50-second single-sentence attempt against a loaded model. Therefore the three-scene live output benchmark is not certified. The API path and mocked job workflow pass tests.

## How the pieces flow together

```text
Author-owned manuscripts / imported books
                 |
                 v
Series Vault -- immutable snapshots / source hashes / edition metadata
         |                                           |
         v                                           v
Deterministic source discovery                On-demand local Deep Read
         |                                      (optional local Ollama)
         +-----------------+-------------------------+
                           |
                           v
             Evidence candidate inspector
                           |
                  Author stages proposal
                           |
                           v
              Canon Graph pending review
                     |             |
                Reject         Approve (explicit)
                     |             |
                     +-------------+
                           |
                           v
             Unified Story State API (read-only)
                           |
            +--------------+--------------+
            |              |              |
       Universe/Edges  Character Minds  Threads/History
            +--------------+--------------+
                           |
                    Time Machine lens
                (book + sequence filtering)
```

**Privacy and continuity:** The app does not rewrite manuscript files, auto-approve a model's suggestions, equate character belief with world truth, or use future-book facts at an earlier time point. Changed linked files are flagged without mutating the archived evidence.

## Technical work

| Area | Implementation |
| --- | --- |
| Unified projection | `backend/app/series_story_state.py` — one indexed canon read, scope/temporal filters, conflicts, profiles, links, threads, stale sources, scene points |
| Source discovery | `backend/app/series_discovery.py` — full-source literal scan, exact offsets, reviewed-claim de-duplication, book/page scope and safety caps |
| Discovery API | `GET /api/series/{id}/discover?book=&limit=&offset=` — read-only |
| Review handoff | Existing `POST /assertions` creates *proposed* only; existing `POST /assertions/{id}/review` approves/rejects |
| Deep Read | Existing selected-source Ollama suggestion endpoint, local/optional and source-checked |
| Visual graph | `StoryConstellation.tsx` — actual linked edges, interactive selection, collision relaxation |
| Discovery studio | `StoryDiscovery.tsx` and `StoryDeepRead.tsx` — integrated lead inspector and opt-in review |
| Main shell | `StoryObservatory.tsx` — perspective filters, portals for immersive mode, Escape exit, source drilldown and book/scene scrubber |
| Quality lab | `story_generation_eval.py`, `story_benchmark_jobs.py`, `StoryModelLab.tsx` — explicit local benchmark and status |

## Tested evidence

- **Production frontend:** TypeScript + Vite production build passed.
- **Backend Part 1 regressions:** 35 focused tests passed, including source-offset validation, approval gating, time boundaries, portability, local-only benchmark jobs, discovery, and story-state projection.
- **Synthetic scale:** 12 volumes, 1,000 named characters, 2,400 accepted assertions. Two selected-book projections finished in **0.133s** and **0.150s** on the test machine; a stress test asserts the 10-second safety ceiling.
- **Real browser audit:** 1440px desktop, 900px tablet and 390px mobile; explicit staged proposal flows, time-scrubbed state, fullscreen enter/Escape exit, model discovery and graph navigation.
- **Specific UI regressions fixed:** 608px mobile grid intrinsic overflow despite 390px document scroll width; fullscreen graph collapsed to a 2px stage due grid shrinkage; graph card overlap. All were caught and verified using DOM bounding rectangles, not solely screenshots.
- Synthetic screenshots are captured from the app running against a dedicated scratch series, not synthetic illustrations and never the author's private manuscripts.

## Current screenshots

- [Universe at 1440px](screenshots/part1-rebuild/01-world-1440.png)
- [Manuscript discovery overview](screenshots/part1-rebuild/02-discovery-1440.png)
- [Discovery ledger + source inspector](screenshots/part1-rebuild/12-discovery-ledger-detail.png)
- [Local Deep Read controls](screenshots/part1-rebuild/13-deep-read-controls.png)
- [Mobile discovery](screenshots/part1-rebuild/14-mobile-ledger.png)
- [Mobile evidence review](screenshots/part1-rebuild/15-mobile-inspector.png)
- [Immersive constellation and relationship evidence](screenshots/part1-rebuild/16-immersive-graph.png)
- [Character Minds](screenshots/part1-rebuild/17-character-mind-evidence.png)
- [Plot threads](screenshots/part1-rebuild/18-story-thread-rails.png)
- [Book/scene time navigation](screenshots/part1-rebuild/06-book-scene-time-1440.png)
- [Model Lab](screenshots/part1-rebuild/11-local-model-lab-1440.png)

## Release gates still requiring closure

1. **Real Ollama scene-generation quality and throughput**: the workstation is not returning generation requests reliably; no actual long-form model benchmark report can be certified without a passing run.
2. **True semantic full-manuscript extraction / edition reconciliation**: source discovery is conservative and capped (4 million characters per source, 1,200 candidate ceiling, 250 results/page). Ambiguous or implied story facts still require author review or manual citation.
3. **Accessibility**: desktop/mobile click and keyboard Escape checks passed, but independent screen-reader/zoom/assistive-technology assessment has not yet been completed.
4. **Human author acceptance**: no professional-author usability study or confidence calibration on real licensed manuscripts has been completed.

Do not describe this PR as a fully certified commercial release or merge it automatically. The visible app and author workflows are much more complete, and the remaining gates are explicit rather than concealed.

## Whole-application regression check and baseline comparison

On the Windows development machine the full backend suite collected **648 tests** and returned **634 passed, 6 skipped, 8 failed**. The failing tests were limited to `test_book_jobs.py` and `test_book_reviews.py`. Their teardown repeatedly raised `PermissionError [WinError 32]` while Python attempted to delete temporary `.ember/story.db` SQLite files that still had open handles.

To distinguish a new Part 1 defect from existing Windows test infrastructure issues, the same two test modules were run against a separate, clean worktree of commit `97707fe` **before this rebuild**. They reproduced the **exact same eight failures** (8 failed, 4 passed). Therefore these are not introduced by this PR; they remain real repository-level quality debt and should be fixed independently, not silently excluded. This PR must not be represented as passing the entire backend suite.

The focused Part 1 regression modules did pass **35/35**; the new source discovery, stress, story-state, and benchmark code was also checked with Ruff, with no remaining findings in those changed Python files.
