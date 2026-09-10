# EmberWriter Product Roadmap

EmberWriter is being built as one integrated local-first author environment rather than a collection of disconnected AI tools. The target combines four product tracks:

1. **Authoring & Organization** — Scrivener-class project management and drafting.
2. **Editorial Analysis** — AutoCrit-class manuscript diagnostics and revision coaching.
3. **Story Intelligence** — EmberWriter's structured canon, character knowledge, relationships, timeline, setup/payoff, and retrieval engine.
4. **Prose & Intimacy Craft** — voice-aware generation, scene architecture, relationship chemistry, escalation, and aftermath for adult fiction.

The manuscript remains authoritative. AI-derived state is inspectable/correctable. Durable story data stays in readable files wherever practical, with SQLite used for fast indexes, snapshots, caches, and rebuildable analysis.

## Product principles

- **The author owns the book.** Analysis proposes; the author decides. AI-derived facts never outrank manuscript or pinned author canon.
- **Local-first by default.** Manuscript, story bible, craft profiles, relationship profiles, plans, and exports live in the project folder.
- **One story model, many tools.** Binder, Corkboard, Outliner, editor, continuity, Scene Architect, chemistry, and editorial reports should all operate on the same project graph.
- **Voice before volume.** Generation should imitate the book's established technique and character voices, not generic model prose.
- **Continuity is temporal.** What is true, what a character knows, and what a relationship means can all change chapter by chapter.
- **Explicitness is not a substitute for craft.** Adult-fiction heat controls intensity; tension, character psychology, voice, relationship history, and aftermath control whether a scene works.
- **No destructive automation.** Rewrites, aftermath updates, canon changes, and editorial fixes are previewable/reversible.

## Track A — Scrivener-class authoring & organization

### Project Binder / Draft hierarchy
- Hierarchical manuscript tree: book > part > chapter > scene > text document.
- Research, characters, locations, notes, trash, and arbitrary custom folders.
- Drag/drop reordering that changes manuscript order without renaming source files unnecessarily.
- Multi-select operations and bulk metadata edits.
- Stable internal node IDs separate from display names and filenames.
- Collections / saved searches that reference Binder nodes without duplicating files.

### Corkboard
- One index card per Binder document/scene.
- Editable synopsis, status, label, POV, location, timeline date, relationship focus, heat/tension, and custom metadata.
- Drag cards to reorder the manuscript.
- Freeform planning board for non-manuscript ideas.
- Relationship/plot-thread overlays from Story Intelligence.

### Outliner
- Spreadsheet-like manuscript overview with configurable columns.
- Word count, target, status, label, POV, participants, location, date/time, tension, scene purpose, unresolved threads, continuity warnings, editorial score, revision state, and custom fields.
- Sort/filter/group without destructively changing manuscript order unless explicitly requested.
- Save views as named layouts.

### Editor
- Rich-text and Markdown-friendly editing while retaining portable source files.
- Scene/document tabs or history stack.
- Split editor and quick-reference panes.
- Typewriter scrolling, focus/distraction-free mode, line/paragraph focus.
- Comments, annotations, bookmarks, inline notes, footnotes where appropriate.
- Find/replace across project, regex option, saved searches.
- Document and project statistics.
- Word-count goals, session targets, deadlines, streaks, and writing history.
- Dictation/speech-to-text adapter.

### Metadata & templates
- Labels, status, keywords/tags, custom metadata types, custom icons.
- Character/location/scene templates.
- Project templates.
- Metadata-aware search, collections, Outliner columns, and Compile filters.

### Revision safety
- Manual snapshots and automatic pre-rewrite/pre-generation snapshots.
- Snapshot compare/diff and restore.
- File/document version history UI.
- Trash/recovery rather than immediate deletion.

### Compile / export
- Compile manuscript from Binder selection and metadata filters.
- Section layouts and separators.
- Front/back matter.
- DOCX, PDF, EPUB, Markdown/plain text, and print-oriented exports.
- Manuscript/submission presets plus custom compile profiles.
- Per-format typography and page-layout controls.

## Track B — AutoCrit-class editorial analysis

### Summary / manuscript health
- Overall manuscript dashboard with prioritized revision recommendations.
- Scores are diagnostic trends, never a universal definition of good writing.
- Chapter/scene heatmap and click-to-source navigation.
- Baseline snapshots so an author can compare revision passes.

### Pacing & momentum
- Sentence-length variation.
- Paragraph-length variation.
- Chapter-length variation.
- Slow/fast passage detection.
- Action/dialogue/interiority/description balance.
- Scene tension trajectory and dead-zone detection.
- Story-level pacing mapped against structural beats.

### Dialogue
- Dialogue percentage/balance.
- Dialogue tag frequency and variety.
- Adverbs attached to dialogue.
- Speaker-attribution clarity.
- Talking-head scenes / insufficient grounding.
- Character-specific dialogue fingerprint and voice drift.
- Interchangeable-dialogue detector: could another character say this unchanged?

### Strong writing
- Adverbs.
- Passive indicators.
- Tense consistency.
- Showing/telling indicators.
- Cliches.
- Redundancies.
- Filler/weasel words.
- Filter words and distancing language.
- Abstract emotional labeling vs embodied evidence.
- Excessive qualifiers/intensifiers.

### Word choice
- Repeated sentence starters.
- Initial pronoun/name patterns.
- Generic descriptions.
- Weak/overused verbs.
- Personal crutch phrases.
- Power-word/precision opportunities.
- Sensory vocabulary balance.
- Metaphor/image-family consistency.

### Repetition
- Word frequency.
- Repeated nearby words.
- Repeated phrases/n-grams.
- Phrase frequency across manuscript.
- Character-specific repeated gestures/reactions.
- AI-tell detector for repetitive generated phrasing.

### Readability & mechanics
- Readability metrics.
- Sentence complexity and length distribution.
- Spelling/grammar adapter.
- Punctuation-pattern analysis.
- Paragraph/sentence fragments as intentional-vs-accidental signals.

### Genre / style benchmarking
- Genre profiles stored as transparent benchmark data.
- Compare dialogue balance, sentence/paragraph distributions, pacing, description density, chapter length, and other measurable traits.
- Optional author/book corpus profiles only where licensing/data provenance permits.
- Benchmarking is advisory; Voice Lock and the author's own baseline can override genre norms.

### Story Analyzer
- Beat-sheet overlays: plot-centered, character-centered, romance, mystery, horror, and custom structures.
- Character arc analysis.
- Conflict progression.
- Plot-thread setup/payoff tracking.
- Stakes progression.
- Promise/payoff and reveal timing.
- Ending/payoff diagnostics.
- Jump directly from issue to manuscript location.

### Reader simulation
- Configurable alpha/beta reader personas.
- Chapter-level reader reactions and questions.
- Confusion/boredom/anticipation tracking.
- Spoiler-aware reader knowledge state.
- Compare reader reactions between manuscript revisions.

### Voice reader
- System TTS adapter first; optional premium/local neural TTS later.
- Playback from selection, scene, chapter, or compiled manuscript.
- Speed/voice controls and sentence highlighting.

## Track C — Story Intelligence

Already underway:
- Source-aware narrative memory.
- Character dossiers/state/knowledge.
- Relationship history.
- Scene Architect.
- Voice Lab / Voice Lock.

Planned:
- Pinned/correctable canon that explicitly outranks inferred memory.
- Temporal character state and knowledge-at-chapter queries.
- Unified timeline with relative/absolute dates and contradiction detection.
- Setup/payoff graph.
- Secrets/reveals graph.
- Object ownership/location history.
- Injury/condition/power progression.
- World-rule validation.
- Relationship graph with history playback.
- Semantic + lexical retrieval with explainable context selection.
- Series-level canon across multiple books.

## Track D — Prose & Intimacy Craft

Already underway:
- Heat levels and tension curves.
- Voice Lab / Voice Lock.
- Character-dossier injection.
- Craft Pass.
- Scene Architect.

v0.5:
- Pairing/group-specific chemistry profiles.
- Author-controlled relationship boundaries.
- Attraction/verbal/initiation/response signatures.
- Trust and vulnerability state.
- Relationship-specific lore/magic resonance.
- Milestone history.
- Next meaningful escalation guidance.
- Aftermath analysis with explicit author approval before profile updates.

Later:
- Character-specific intimacy signatures independent of any one pairing.
- Multi-person relationship network state without collapsing it into pairwise romance.
- Jealousy/territorial tension as continuity state rather than automatic melodrama.
- Consent/choice continuity without treating prior intimacy as blanket permission.
- Intimacy pacing across a whole novel: avoid clustering repetitive payoff scenes.
- Relationship aftermath reminders and unresolved conversations.
- Craft diagnostics specific to intimate prose: mechanical choreography, repetitive reaction language, anatomy-vs-emotion imbalance, generic dirty talk, spatial confusion, premature peak intensity, missing aftermath, and voice drift.

## Milestone sequence

### v0.5 — Relationship Chemistry + Aftermath
Pairing profiles, inference, author editing, chemistry-aware Writer/Scene Architect, aftermath proposal/apply workflow, milestone history.

### v0.6 — Binder + Project Graph
Stable document IDs, hierarchical Binder manifest, drag/reorder API, metadata model, collections foundation, safe trash/recovery. This becomes the structural spine for Corkboard, Outliner, Compile, and analysis navigation.

### v0.7 — Corkboard + Outliner + Metadata
Visual cards, configurable metadata columns, filters, saved views, scene synopses, targets/status/labels, story-intelligence overlays.

### v0.8 — Editorial Engine I
Deterministic local reports: repetition, sentence/paragraph variation, adverbs, passive indicators, filler, dialogue tags, dialogue balance, readability, tense indicators, POV heuristics. Interactive click-to-source results.

### v0.9 — Canon + Timeline + Setup/Payoff
Pinned canon, temporal state, timeline UI, secrets/reveals, setup/payoff graph, contradiction repair workflow.

### v0.10 — Editorial Engine II / Story Analyzer
Pacing heatmaps, character arc/conflict/thread analysis, structural beat overlays, revision dashboard, manuscript health trends.

### v0.11 — Revision Workspace
Snapshot diff UI, comments/annotations/bookmarks, project search/replace, revision passes, issue queues, before/after analysis comparison.

### v0.12 — Compile + Publishing
Binder-aware compile pipeline, DOCX/PDF/EPUB, section layouts, front/back matter, presets, project export/backup.

### v0.13 — Reader Lab + Voice Reader
Configurable alpha/beta reader simulations, spoiler-aware reader state, revision comparisons, TTS playback.

### v0.14 — Desktop Polish
Native Windows packaging, graphical import/recovery, file watching, crash recovery, update mechanism, OS integrations, performance work for 100k-300k+ word books.

### v1.0 — Integrated Author Studio
Scrivener-class organization + AutoCrit-class editorial diagnostics + EmberWriter story intelligence + model-agnostic local AI writing/craft in one coherent workflow.

## Competitive target

EmberWriter should not merely clone Scrivener and AutoCrit. The advantage is that organization, editorial diagnostics, generation, continuity, and story-state reasoning share the same source-aware project model. An editorial warning can open the exact scene; Scene Architect can see the same relationship/timeline facts; Writer can preserve the same voice profile; Aftermath can propose state changes; Corkboard and Outliner can visualize those changes; Compile can filter by the same metadata. The author should never have to maintain the same story truth in five disconnected tools.
