# EmberWriter: What We Build Next

**Product definition:** a writing-first studio in which authors can write every line,
delegate a scene, or direct a complete novel. Authors control canon, voice, edits,
publication, and rights. AI-generated prose is a candidate, not an accepted master.

This roadmap is deliberately more ambitious than copying AutoNovel. It prioritizes
quality, creative control, offline ownership, and finished-book production.
Every future feature should expose provenance, uncertainty, review/undo, and privacy.

## P0 — Reliability and a seamless whole-book production loop

1. **End-to-end book production conductor (first guided pipeline shipped):**
   Book Studio drafts, optional local independent reader critiques, explicit
   author approval gate, whole-book Editorial Board and Production Readiness
   handoff now share a durable supervisor and a bounded checkpoint journal.
   Next: linked author-controlled revision proposals, canon impact tasks,
   audiobook handoff, per-stage retry settings and finalized export packaging.
2. **Long-running job supervision:** persisted token/time budgets, retry policies,
   resource-aware model scheduling, crash recovery, durable event log,
   pause/resume/cancel and per-chapter diagnostics.
3. **Source-of-truth audit:** one canonical chapter selector (Binder order),
   explicit Book Studio candidate versus approved manuscript status, no duplicate
   chapters in compile or reports, version hashes between every stage.
4. **Whole-book context architecture:** chapter summaries, timeline state,
   relationship graph, accepted canon, unresolved promises, scene beats, and
   retrieval priority. Prompt assembly must be bounded, inspectable and testable.
5. **Story promise coverage:** trace promise planting and payoff with exact source
   evidence. Suggest candidates, never declare fulfillment without author sign-off.
6. **Narrative dependency graph:** when a character, secret or plot event changes,
   identify potentially affected future scenes and generate review tasks.
7. **Chapter goals vs manuscript coverage:** compare each chapter brief to
   on-page evidence for required beats, missing reversals, promises and payoffs.
8. **One-click safety snapshot before large operations:** encrypted backup option,
   restoration preview and source checksums, all local.
9. **Safe provider boundaries:** explicitly model local vs remote vs Ollama-hosted
   aliases in one central policy. Fail closed for private, unattended workflows.
10. **No manuscript serialization into diagnostics:** default redaction of content,
    prompt history and logs outside project-owned storage.

## P1 — Writing craft and serious editing

11. **Grammar backend:** optional fully local LanguageTool or equivalent,
    installable with Pinokio, with paragraph spans, suggestions, ignored rules,
    project-specific dialect, style dictionary, and opt-in batch review.
12. **Deep repetition analysis:** word/phrase echoes and semantically repetitive
    passages across scenes; evidence, window sizes and false-positive dismissal.
13. **POV/tense drift auditor:** sentence-grounded candidate shifts with author
    exemptions for flashbacks, free indirect style and unreliable narrators.
14. **Character voice differentiation:** dialogue attribution and comparison
    across characters, tracking lexical choices and speech habits; avoid asserting
    uncertain speaker identity as fact.
15. **Show/tell and abstraction review:** anchored suggestions with alternatives;
    never strip deliberate summary from pacing or literary voice.
16. **Pacing & scene-turn map:** identify local conflict/goal/stakes/decision/outcome,
    compare subjective tension with scene-level structural evidence.
17. **Emotional change tracking:** who begins the chapter in what emotional state,
    what changed, and which passage supports that claim.
18. **Character agency audit:** distinguish mere character appearance from
    choices, consequences, and meaningful influence on the plot.
19. **Relationship evolution:** explicit between-character state changes,
    boundaries and trust, with author approval and narrative-source citations.
20. **Foreshadowing and payoff planner:** plant, reinforce, complicate,
    subvert, pay off; warn about unreviewed promises without automatic certainty.
21. **Genre-specific rubric packs:** mystery, fantasy, horror, romance, thriller,
    literary fiction and hybrid. Rubrics are user-editable, not defaults imposed.
22. **Sensitivity/context review:** flag continuity or representation risks
    with uncertainty, without reducing characters to demographic templates.
23. **Independent reader ensembles:** multiple truly independent evaluations,
    disagreement view and aggregated *evidence*, not arbitrary consensus.
24. **Editorial A/B testing:** revisions next to originals, blind reading,
    measurable deltas, and author disposition history.
25. **Voiceprint evolution:** compare against multiple author-selected references,
    by POV and character rather than imposing a single global style.
26. **Local style dictionary:** forbidden generic phrases, preferred spellings,
    invented vocabulary and manuscript-wide terminology consistency.
27. **Sentence-level diffs:** word/character granularity with keyboard
    acceptance controls and persistent undo/revision history.
28. **Revision plateaus:** stop proposing repetitive changes when there is no
    accepted improvement, not when an arbitrary score increases.

## P2 — Worldbuilding, research and creative control

29. **Dynamic story bible:** typed canon facts with sources, version history,
    certainty, dates, relationships and conflicting-source detection.
30. **Character dossiers with lifetime arcs:** goals, flaws, secrets, wounds,
    contradictions, values and changing relationship boundaries.
31. **World and geography timeline:** travel duration and physical constraints,
    dates, seasons, tides, star maps and location continuity.
32. **Research capture:** user-approved citations and reference cards with
    provenance; no undocumented Internet import into private stories.
33. **Interactive mystery board:** questions, suspects, clues and revelations
    connected to chapter evidence.
34. **Choice exploration:** alternate plot branches and expected consequences;
    authors select branches before drafting.
35. **Nonlinear book revisions:** move scenes, restructure chapters and
    recalculate chapter-state dependencies with preview and undo.
36. **Series continuity:** book-to-book canon versioning and spoiler boundaries,
    without cross-project reads unless explicitly linked by the author.
37. **Local writing game:** personal milestones, sessions and focus mode;
    optional motivational elements, never manipulative metrics.

## P3 — Audiobook production

38. **Natural offline voices:** optional, licensed Piper/Kokoro or equivalent
    voice assets with install/test and hardware-aware fallback.
39. **Chapter narration queue (first pass shipped):** Binder-ordered local
    batch, progress, pause/resume, restart recovery, source fingerprints and
    chapter ZIP are implemented. Next: robust subprocess cancellation,
    per-chapter retry controls, performance budgeting and monitoring.
40. **Voice casting:** author assigns voices to characters; dialogue attribution
    is editable and cannot silently infer a cast.
41. **Pronunciation lexicon:** fictional names and invented languages with
    IPA/phonetic previews and per-chapter overrides.
42. **Performance markup:** pauses, pace, emotion and pronunciation under
    explicit author direction; no automatic dramatic rewriting.
43. **Mastering pipeline:** loudness targets, peak limits, silence cleanup,
    chapter alignment, sample review and consistent metadata.
44. **Retail audiobook formats:** MP3 distribution packages, M4B chapters
    and metadata where supported, verified against current retailer specs.
45. **Accessibility:** navigation markers, chapter lists, transcripts and
    metadata; legal voice/licensing checks before distribution.

## P4 — Publishing and business of authorship

46. **Book-specific production templates:** reflowable EPUB, print trim/bleed,
    headers/footers, front/back matter, scene ornaments and typographic proof.
47. **Preflight integration:** link metadata, Binder order, editorial QA, cover
    checks, audiobook readiness and per-retailer validation in one review flow.
48. **Retailer-specific test matrices:** current KDP/Ingram/Apple/Kobo
    requirements, with evidence of when each rule was last verified.
49. **Accessibility validation:** EPUBCheck/ACE, reading order, alt text,
    contrast and semantic navigation for books and marketing assets.
50. **Distribution packager:** verified ISBNs, covers, interiors, descriptions,
    keywords and checksum manifests with rights/license sign-off.
51. **Companion author site:** optional static book landing page, newsletter
    signup configured by the author, press kit and storefront links.
52. **Translation/localization:** human-reviewed target-language editions,
    terms glossary, character voice and edition provenance.
53. **Performance & launch insights:** offline planning and simple sales tracking
    by user import; no private telemetry unless the author explicitly enables it.

## Engineering acceptance criteria

Every release should demonstrate:
- A clean installation from the public Pinokio launcher, not merely a developer PC.
- Unit and API tests using synthetic content only; no real manuscripts in CI.
- Production frontend build and publication-source privacy scan.
- Separate Demo and Private roots remain isolated across upgrades/restarts.
- Long operations are observable, restartable, bounded, and cancellable.
- Author edits are never overwritten without an explicit, reversible action.
- Every AI finding states its evidence, uncertainty and source version.
- A feature that requires external network traffic must say so, require opt-in,
  and explain what content may leave the machine.
- Product claims distinguish functional first versions from professional-grade
  editing, narration, or retailer-certified publishing.
