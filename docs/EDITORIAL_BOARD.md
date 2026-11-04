# Whole-Book Editorial Board

**Author-owned manuscript review, not a quality score or automatic rewrite.**

Located at **Plan → Editorial Board**. It combines the already-functional
Prose Editor, Style Bible, independent Reader Panel, and Story Arc Investigator
into a chapter-by-chapter editorial control tower.

## Workflow

1. Choose an expected chapter POV and tense, or leave these off to avoid
   speculative drift warnings.
2. Select **Scan entire book**. This runs locally and stores a compact
   fingerprinted baseline in the current project's `.ember/editorial-board`.
   The baseline contains chapter paths, hashes, counts, and scan preferences,
   **not a serialized copy of the manuscript**.
3. See all current authored chapters and Book Studio candidates in manuscript
   sequence. Each row reports word count, unresolved prose and terminology
   findings, possible mechanical repairs, current independent reader coverage,
   and current story-arc analysis coverage. Source changes invalidate the
   reader/arc coverage, rather than silently treating old assessments as current.
4. Use the priority shortcuts to review chapters with the highest count of
   proposed mechanical corrections. This is task triage, **not ranking prose**.
5. Select individual, *currently pending* mechanical corrections for **one
   chapter at a time**. Preview the complete original and proposed chapter
   side-by-side. Overlapping proposed changes cannot be batch-applied.
6. **Approve** the selected changes explicitly. EmberWriter checks both the
   exact source SHA-256 fingerprint and the previewed proposed SHA-256
   fingerprint before writing. It uses `storage.save_text` for manuscript
   chapters, which creates restorable snapshots, and `edit_candidate` for
   pending Book Studio chapters, which archives their original candidates.
   A batch update does not implicitly approve an AI-generated chapter.
7. Non-mechanical POV and tense warnings and Style Bible exceptions must be
   reviewed in their dedicated panels. The Editorial Board provides direct
   shortcuts that preserve the targeted chapter wherever possible. It does not
   convert suggestions to approvals without your decision.
8. Export a Markdown report or use the saved scan history to compare counts
   across review passes.

**Publishing connection:** the Production Readiness Gate warns if a previously
saved whole-book editorial baseline is stale because chapter content changed.
A manuscript without an editorial baseline is not locked from publishing.
The author remains responsible for actual publication, including intentional
style exceptions.

## Limits and reliability

- Local only. No external grammar APIs or model calls from this dashboard.
- 120 chapters; 12 MB aggregate chapter text; 6,000 findings; at most 100
  non-overlapping corrections per author-approved batch.
- Prose Editor is a transparent heuristic reviewer, *not* LanguageTool,
  Grammarly, a dictionary, or a comprehensive grammar judge.
- Style Bible matching is literal; narrative interpretations are subjective.
- A chapter is scanned again on each preview and approval. A stale edit,
  nonmechanical selection, duplicated item, overlapping edit, or changed
  preview is rejected.
- Changes in other tools are detected from the source hash; however
  simultaneous direct writes in another process outside the same local
  service should be avoided during the brief final approval write.
- Existing per-project decision histories stay in their original modules.
  Editorial Board does not clone or overwrite those decision records.
- Scans are synchronous and bounded. Very large manuscripts near the
  configured limits may take noticeable time to analyze.

The synthetic integration suite covers cross-project isolation, mixed
Style Bible and Prose Editor findings, edits across multiple chapters,
multiple corrections applied with one archival snapshot, author rejection
on stale source, candidate archival without approval, analysis coverage
invalidated by author edits, and preflight freshness.
