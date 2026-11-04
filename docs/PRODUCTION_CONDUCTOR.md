# Author-led Book Production Conductor

Located under **Plan → Book Production Conductor**.

EmberWriter already has a durable Book Studio drafting queue, individual
Reader Panel evaluations, revision proposals, the Whole-Book Editorial Board,
and the Production Readiness Gate. This feature connects those engines into
one checkpointed author-led book-production journey.

## Actual working lifecycle

1. **Plan:** the author creates or revises a Book Studio plan with one to
   eighty chapters, premise, voice, and chapter briefs.
2. **Start production:** choose an installed *local* Ollama model and zero
   to three independent reader personas. This is a deliberate opt-in.
3. **Draft:** the conductor supervises the existing local, restart-resumable
   Book Studio queue. It saves only draft *candidates*. A queued or running
   drafting task already present in Book Studio cannot be silently hijacked;
   choose one workflow at a time.
4. **Review:** after all chapters are drafted, the conductor sequentially
   requests independent local reader evaluations for each unapproved current
   candidate, using exact-evidence checks from the existing Reader Panel.
   Reviews are keyed by candidate fingerprint and persona so a revision
   invalidates old reader coverage and can be evaluated again. An error or
   rejected model output pauses production as **needs attention**.
5. **Author approval gate:** the conductor becomes **awaiting author**.
   Nothing is approved here. The author edits candidates, responds to reader
   findings, requests optional revisions through Revision Workbench, rejects
   failed prose, and explicitly approves completed chapters in Book Studio.
6. **Continue:** the conductor checks the plan for unfinished chapters, new
   candidate versions needing critique, or author-approved manuscripts.
   Resume produces only what the author has opted into.
7. **Editorial:** only after *all* chapters are approved does it run the
   deterministic Whole-Book Editorial Board scan and save the scan ID.
8. **Production preflight:** it runs the existing Production Readiness Gate
   and records blocker/warning totals, then creates a **publishing handoff**.
   The author reviews details and exports the book manually from Publish.

A completed handoff detects if the manuscript changed afterward and warns
that the author should continue the conductor to refresh editorial checks.

## Durable operation and privacy

The job record lives only inside the project, in
`.ember/production-conductor.json`. It contains an Ollama model tag, local
provider endpoint, selected reader personas, source hashes, task checkpoints
and a bounded 120-item event journal with timestamps. **It does not store
prompts, manuscripts, passwords, or API credentials.**

- A browser may be closed while queued/running work continues on the local
  application service. A paused job stays paused after restart.
- On service startup, only previously queued/running, explicitly opted-in
  work resumes. When interrupted mid-review, the current evaluation may be
  repeated; reader findings are linked to the actual candidate source.
- Pausing while generating a chapter or reviewing a candidate may finish
  the current operation. Resuming afterward rechecks all chapter statuses.
- The conductor never overwrites a canonical chapter and never uses external
  LLM endpoints for its generation or reader evaluations.
- Multiple concurrent production conductors for a single project are rejected.
  Separate projects have independent checkpoint files.
- All story content and checkpoints stay in the selected project; no private
  manuscript or demographic information is used in test fixtures or release
  assets.

## Long-book continuity improvements

Draft prompts now reserve space for the actual immediately preceding
chapter ending, a **source-grounded rolling excerpt digest** of opening
and recent chapters, up to twelve explicitly author-tracked open promises,
and author-supplied world/character/style/timeline documents. The complete
context is bounded at 16,000 characters. A raw excerpt is explicitly not
declared an exhaustive factual summary. It is a first pragmatic step toward
full semantic memory, not a resolved cross-book retrieval engine.

## Known limitations

The conductor does not auto-approve reader criticism, select suggested
revisions, rewrite approved prose, submit files to retailers, or claim
professional grammar validation. Reader review runs after drafted candidates,
not concurrently with the writer; in large books this deliberately serial
process can be substantial. The production preflight is advisory. The current
system lacks per-step cost/token accounting, GPU contention-aware scheduling,
a full local grammar dictionary, semantic character-state memory, and fully
automated professional audiobook mastering.

Those are distinct further engineering milestones, not capabilities implied
by this release. All generation/tested end-to-end behavior is verified using
**synthetic stories and mocked Ollama responses**; real book-long model
performance will vary with the installed local model and its context capacity.
