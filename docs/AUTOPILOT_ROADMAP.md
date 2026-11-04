# EmberWriter Autopilot — AutoNovel feature parity and beyond

Reference: https://github.com/NousResearch/autonovel (reviewed 2026-11-04; README and PIPELINE.md). This is a **feature design comparison**, not a code port. We are building an original, locally hosted author-first implementation that uses EmberWriter's existing modules. No AutoNovel API keys, prompts, copyrighted story material, or dependencies are copied into EmberWriter.

## Non-negotiables

- **Author is the director:** every generated draft is a proposed candidate; never silently replace a manuscript. Show readable diffs, accept/reject, revision checkpoints, and rollback.
- **Local privacy by default:** use Ollama or another explicitly configured loopback runtime. No remote provider fallback, analytics upload, or cloud storage. If an author chooses remote models or ElevenLabs/fal, disclose which text/audio/image prompts leave the machine and require a one-time opt-in per destination.
- **Separate demo/private data roots:** the pipeline inherits the running server's `EMBER_DATA_DIR`; no cross-library indexing, retrieval, or ingestion. Demo sample is generated locally.
- **Quality is not one scalar:** combine deterministic issue counts, independent reader voices, project-level promises/payoffs, and author judgment. Separate grounded evidence from suggestions. Store reasoning and findings locally.
- **Bounded automation:** max attempts, budgets, cancellation, persistence after crashes, and a stop condition for score plateau or low-confidence findings.
- **Reproducibility:** model/version/prompt templates, source hashes, generation provenance, explicit approval ledger, and local snapshots before writes.
- **Windows/Pinokio:** backend and frontend must build on Windows x64; no LaTeX or hosted service is a mandatory install dependency.

## Capability map

| AutoNovel capability | Current EmberWriter | Direction |
|---|---|---|
| Story seed ideation | Brainstorm/AI Studio | Build 10-seed workshop, weighted premise discovery and author selection |
| World bible generation | World workspace, atlas, knowledge | Multi-pass foundation compiler with citation to author canon |
| Character registry | Characters, story intelligence, voice profiles | Character constellation with want/need/lie/wound and relationship change graph |
| Outline + foreshadowing ledger | Planning Hub, development beats/threads | Setup→payoff coverage graph, dangling promises, continuity debt |
| Canon/hard fact crosscheck | Story memory, continuity tools | Canon diff/approval, cross-layer conflict graph with source anchors |
| Voice discovery | Voice fingerprint + style fidelity | Trial passages and A/B voice lab with fingerprint-based comparison |
| Sequential chapter drafting | AI Studio + scene planner | Batch writer with per-chapter context window, cancel, preview and retry |
| Mechanical anti-pattern checks | Prose quality + editorial reports | Combined offline chapter diagnostics, transparent thresholds |
| LLM editorial judge | Editorial reports/reader personas | Opt-in multi-model rubric with citations, confidence and disagreement |
| Adversarial cut proposals | Editorial fixes | Classified cuts (repetition, overexplanation, structure), patch preview |
| Pairwise Elo chapter tournament | Not present | Optional blind comparison, avoid treating Elo as objective truth |
| 4+ reader persona panel | Reader Studio has 3 personas | Extend personas and consensus dashboard, specificity/evidence ratings |
| Iterative briefs and revisions | Editorial fix + revision history | Revision brief queue, guarded application, approval and rollback |
| Independent dual-review panel | Reader Studio/editorial | Critic/professor personas; stop when major actionable findings cease |
| Score plateau stop | Not present | Score trajectories with 2-cycle plateau, budget and diminishing-returns halt |
| Multi-stage autonomous pipeline | Individual studios only | Central mission scheduler, resumable jobs, author gate per stage |
| Art directions, cover and ornaments | Visual Studio and Cover Studio | Curation, style-safe prompt library, vector ornaments and print wrap |
| Print PDF/ePub output | Publishing Studio | Typography presets, KDP/Lulu validation, proof preview and KDP-safe bleed |
| Audiobook script and multi-voice audio | Not yet fully implemented | Speaker-attributed segmenter, local TTS first, optional user-approved provider |
| Landing page | Preview/Distribution Studio | Exportable static landing site (no tracking), optional sample chapter |
| ARC/summary & outline rebuild | Story memory summaries + planning | Reconcile draft changes upstream; preserve author-approved canon |

## Release sequence

### A0 — Flight Deck (implemented on feature branch)
- New **Plan → Autopilot** page showing four-stage flight path, author-facing tasks, chapter measurements, local-only mechanical diagnostics and exported Markdown action plan.
- Endpoints: `GET /api/projects/{slug}/autopilot/readiness`, `GET/POST .../autopilot/audits`.
- Data: per-project `.ember/autopilot-audits.json`, bounded to the last 20 saved assessments.
- No provider requests, no manuscript writes. Readiness is heuristic and *not* an LLM literary score.

### A1 — Foundation Lab
- Structured seed concept generator with author selection and saveable alternatives.
- World/characters/outline/canon/voice passes as individually previewable proposals.
- Source-connected foreshadowing ledger, dependencies, truth vs possibility markers.
- Track canon debt when foundation edits affect chapters.

### A2 — Draft Engine
- Author chooses chapter count, target lengths, provider, cadence and constraints.
- A scheduled local job queue with resume/cancel, deterministic checkpoints, retry with bound, progress log, and draft preview. Never automatically overwrite canonical chapters.
- Canon acquisition proposals collected after each chapter; require approval.

### A3 — Revision Engine
- Mechanical checks + independent judge rubric + three/four reader personas.
- Adversarial classified cuts, revision briefs, optional chapter tournaments.
- Patch previews and explicit author confirmation; preserve backups and provenance.
- Multi-cycle convergence graph with plateau/budget/major-finding stopping conditions.

### A4 — Production Engine
- Typeset/publish pipeline with covers, ornamental illustrations, print-wrap validation, audiobook scripts and locally generated narration where available.
- Static author landing page export; independent privacy review for any optional hosted integration.
- End-to-end installation and export tests in a fresh Pinokio runtime.

### A5 — Delight/defensibility
- Creative mission control: task graph, visual story constellation, versioned what-if branches, model-role orchestra, quality radar and editable cost/time budget.
- Offline collaboration via export/import patch bundles, not mandatory accounts.
- Accessibility, keyboard-driven navigation, focus mode and responsive layout.

## Release gates

1. Synthetic-only integration tests and compile/build.
2. Fresh Pinokio install of public source + clean demo seed.
3. Privacy test: personal library absent from demo and no external HTTP in offline mode.
4. Manual UI smoke test on representative project.
5. PR review/merge into `EmberWriter` main, then Pinokio update/upgrade verification. Public launcher remains a separate repository.

## Honest limitations of A0

Current Flight Deck is a planning and assessment cockpit, **not** a full autonomous novel generator. A0 does not make external LLM calls or create book-length manuscripts. Subsequent phases add those capabilities only after safe, reviewable architecture is in place.
