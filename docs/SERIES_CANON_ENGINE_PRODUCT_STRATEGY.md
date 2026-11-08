# Series Canon Engine — the author-first moat for professional novelists

**Product direction:** Make EmberWriter a trustworthy creative operating system for a *career writer*, not an AI prose vending machine. This is a proposed product roadmap; features below marked **Build** are NOT yet shipping.

## North-star demonstration: a sprawling urban-fantasy series

A hypothetical author with a 20+-book supernatural detective series imports every **authorized** manuscript, novella, short story, character notebook, timeline and map. They ask:

> "At the end of Book 12, what does the detective *believe* about his mentor? What is objectively true? Where was the magical artifact last seen? Does the chase I've outlined contradict a previously established rule?"

The answer is not a fluent guess. It gives a **time-bounded, spoiler-scoped, source-linked answer** with conflicting passages highlighted, distinguishes narrator belief from world truth, and provides an author-approved proposed canon correction. A one-click jump opens the exact scene and a reversible, human-reviewed change proposal.

For an author like Jim Butcher, the value proposition would be keeping a large series coherent without turning a trusted writing tool into a machine that imitates or publishes novels under his name. This is a thought experiment and **not** a claim about Jim Butcher's personal desires or endorsement. Do not ingest or expose a living author's copyrighted manuscripts without explicit rights.

## The seven products authors will wish existed

### P0 · The Series Vault (Build)
- Multi-book, multi-series library of novels, novellas, shorts, notes, approved/excluded editions; source hashes and ownership metadata.
- Local-first imports for DOCX, Markdown, Scrivener (where export is available), PDF text and ePub author-owned manuscripts. Never train on author content by default.
- Author-facing access control: personal, collaborator, editor, publisher, audiobook producer; per-document and spoiler boundary permissions.
- Version-aware edition status: published canon > author-accepted manuscript > working draft > speculative alternatives > external research; author can override.
- Portable complete-series backup/restore; no permanent lock-in.

### P0 · Canon Graph, not a wiki (Build)
- Typed entities: characters and aliases; factions, species, locations, objects, magical laws, abilities, secrets, promises, injuries, deaths, debts, relationships, residences, dates, powers, vows and constraints.
- Facts are **events and assertions**, not timeless strings. Each assertion has value, time range, POV/knowledge state, source location, source status, confidence, and deliberate retcon/contradiction flag.
- **Canon is author-committed.** AI extraction creates pending evidence suggestions; a selected source passage never silently becomes immutable truth.
- Queries distinguish *objective lore* from *what a POV knows or falsely believes* and *what the reader has been told*.

### P0 · Continuity Guardian (Build)
- Prewrite scene check and postwrite draft check, both against versioned canon:
  - magic costs and limitations, item custody, locations/routes, ages, dates, injuries/healing, promises, relationship shifts, alliances and character knowledge.
  - "This line is inconsistent with chapters 17 and 22; click both passages" instead of unsubstantiated AI warnings.
- Consequence tracing: if a character dies in Book 8, show the scenes, flashbacks, disguises and future references that might be affected—not automatic replacement.
- Author exceptions: planned unreliable narrator, mistaken claim, red herring, intentional rule break, revision in progress. Suppress only with provenance.

### P1 · Plot Memory & Promise Ledger (Build on existing system)
- Foreshadowing, setups, payoffs, mysteries, emotional debts, artifacts and neglected promises, with *next possible payoff*, risk of forgotten detail, and series-wide search.
- Scene-level "what changed?" ledger: before/after relationship state, objective, consequences, clues introduced and promises incurred.
- Book-by-book and series-wide arc trajectories, configurable pacing, viewpoint and subgenre conventions.

### P1 · Ember as the Series Librarian (Build beyond current helper)
- Book-aware conversations backed by **structured evidence**, not only naive lexical excerpts. Hybrid retrieval: full-text, aliases, entity graph, temporal filters, symbolic rules and semantic embeddings.
- Queries with "as of Book N, Chapter M," spoiler limits, conflicting-claim cards, one-click source, visual timelines and small relationship diagrams.
- "How do I..." answers come from an **indexed, version-matched help library**, with UI targets, guided tours and testable steps. Separate factual app help from imaginative creative suggestions.
- Agent permissions: read, suggest, preview change, and author-confirm write. No unattended canon or manuscript commits.

### P1 · The Voice & Authorship Studio (Build)
- An *author-created* and *author-approved* voice guide that captures observable craft preferences: vocabulary, sentence variation, dialogue rhythm, POV, humor/dread balance, thematic taboos and character voice distinctions.
- Self-comparison against an author's own rights-cleared texts for drift; **do not market imitation of another living writer's distinctive style**.
- Mode A: **Human-authored**: AI can organize, research, critique, proofread, outline and propose alternatives; author produces final expressive text.
- Mode B: **Co-written**: model proposes prose; author can choose, revise and sign off. Record what came from where.
- Mode C: **AI-generated draft under human direction**: model may draft entire chapters/novel, with full manual review and a portable provenance ledger.
- These are workflow modes, **not badges that overrule publisher contracts, Amazon KDP disclosure rules, or copyright law**. Don't claim 100% human authorship merely because a person prompted an AI to generate the text.
- All author edits and AI suggestion replacements are reversible with exact provenance; disclosure export is creator-controlled and factual. Never provide an "AI detector bypass" or fake authorship label.

### P2 · The Franchise Desk (Build)
- Licensing/rights matrix for characters, worlds, text, art, audio; collaborators sign explicit scopes and confidentiality terms.
- Adaptation workspace linking character and scene continuity across screenplays, stage plays, games, audiobooks, graphic novels and translations.
- Narration director remembers actor voice choices, emotional deliveries and pronunciation across every book; source hash & rights checks for synthetic voices.
- Author-owned private beta-reader portal, version-specific comments, spoiler walls, editor-request handoff and contractual review logs.

## High-value interfaces (simple on the surface)

**Start screen**: Continue writing | Explore my world | Fix continuity | Produce & publish. A new writer sees only a small friendly workspace; experienced users reveal advanced production tools.

**Series Desk**: left—book and edition index; center—chronology and relationships; right—Ember citing passage evidence. A slider chooses *reader knowledge at a given point in the series*. No "spoiler leakage" between books.

**Scene Desk**: today’s scene, cast, location, known facts, active promises, atmosphere, POV and risks. Before writing, Ember surfaces up to five relevant facts, each with a source link; the rest stays quiet.

**Review Board**: detected issues ranked as source-grounded conflict, possible conflict, missing source or intentional narrative uncertainty. Proposed revisions always show affected passages and wait for approval.

**Ember companion**: friendly character animation optional/reduced-motion aware, context-aware search/app help, zero surprises about reading or sharing text, and no AI-autonomous edits.

## The first flagship proof (prioritized execution)

1. **Import one complete rights-cleared synthetic series**: 8–12 novel-sized volumes, stories, aliases, timelines, 250+ recurring entities, 1,000+ facts/events, deliberately seeded inconsistencies.
2. **Make 25 reference questions** with ground-truth answers, including "as of" queries, contradictory narrator claims and magic restrictions. Require exact citations and "I don't know" where evidence is absent.
3. **Build author-review canon extraction** into a SQLite event/claim store plus source location and edition index. Never persist model guesses as approved.
4. **Run continuity diff on a new 5,000-word chapter**: no uncited critical warnings, seeded contradictions detected, user-marked exceptions respected, performance acceptable on a CPU-only laptop.
5. **Demonstrate consequences**: change a rule in Book 3, show exactly which later scenes and audio/proof/translation editions must be rechecked. No silent rewrite.
6. **Test 10 professional writers** (published series authors, developmental editors, beta readers) with their own authorized sample material under explicit consent; measure setup time, false alarms, saved time, and willingness to pay.

## Adoption test: why would a bestselling author migrate?

- **Trust:** confidentiality, local-first by default, explicit rights and model access, no hidden training or cloud uploads, deterministic backups/exports.
- **Reliability:** source-anchored lore and continuity errors, no hallucinated canon, no spoilers outside chosen boundaries.
- **Interoperability:** their Word/Scrivener/Final Draft workflows must remain viable. EmberWriter should be an indispensable sidecar *before* they consent to move writing into it.
- **Ownership:** AI never dictates creative intent; the author alone establishes canon and accepts final prose.
- **Economic utility:** clear hours saved on research, series-bible maintenance, continuity, revisions and collaborator handoffs—not vague "100x faster writing."
- **IP & contract safety:** author-facing factual origin records and data processing policies supporting publisher/marketplace disclosure and U.S. human-authorship requirements.

## Competitive positioning

Scrivener is established for the Binder, compilation, snapshots and drafting. Novelcrafter's Codex already offers automatic mentions, cross-series lore entries and progression tracking. Campfire offers maps, calendars, timelines and worldbuilding modules. **Those features alone are not a defensible differentiation.**

Our moat should be the **source-proven, temporal, spoiler-aware Canon Graph plus a trustworthy nonintrusive companion** that works across existing tools and honors human-authored or AI-directed workflows without conflating them.

## Cautions and sources

- Amazon KDP currently requires disclosure of AI-**generated** content even if substantially edited, and excludes genuinely AI-**assisted** content from that requirement: <https://kdp.amazon.com/en_US/help/topic/G200672390>
- The U.S. Copyright Office emphasizes case-by-case human expressive contributions, not prompts alone: <https://www.copyright.gov/newsnet/2025/1060.html>
- Authors Guild recommends guardrails for manuscripts, consent and publishing contracts: <https://authorsguild.org/news/use-of-ai-in-publishing-and-new-model-contract-clause/>
- Novelcrafter's existing Codex: <https://www.novelcrafter.com/features/codex>
- Campfire worldbuilding: <https://www.campfirewriting.com/write>
- Jim Butcher's official series pages (example scale, not an endorsement): <https://www.jim-butcher.com/books/dresden>
