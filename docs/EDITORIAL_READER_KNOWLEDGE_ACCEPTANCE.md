# EmberWriter v0.8 Editorial / Reader / Knowledge Acceptance Gate

This gate supplements `REAL_MANUSCRIPT_ACCEPTANCE.md`. A UI control or successful HTTP response is not sufficient evidence. Run these checks against the real manuscript chosen for final dogfooding.

## Deterministic Editorial Studio

- Run all enabled reports against one real chapter and the whole Draft.
- Confirm every finding records a stable Binder node ID when available, source path, source hash, exact offsets, line, excerpt, severity, message, and suggested review action.
- Click representative findings from every report family and confirm Ember opens the correct source document and selects the flagged prose when the source is still current.
- Resolve and ignore findings, restart EmberWriter, and confirm those workflow states persist in SQLite.
- Edit a reported passage and confirm the old finding becomes visibly stale rather than silently moving to unrelated text.
- Re-run analysis and confirm new findings describe the new content.
- Change project editorial thresholds, restart, and confirm the portable `style/editorial-profile.json` is authoritative.

## AI Reader Panel

Run all three reader perspectives against the real Draft:

1. **Genre Fan** — emotional engagement, favorite moments, chemistry, promises/payoffs, anticipation, and willingness to continue.
2. **Casual Reader** — clarity, confusion, pacing drag, character tracking, accessibility, and willingness to continue without specialist genre knowledge.
3. **Strong Editor** — causality, structure, character arcs, scene purpose, POV, pacing, genre delivery, setup/payoff, and high-leverage revision priorities.

For each reader:

- choose the actual book genre and an optional focus question;
- prove chapters are consumed in Binder compile order with one persisted chapter reaction per step;
- confirm predictions/confusion from earlier chapters are supplied to later chapter reads;
- interrupt a run midway, restart the service, and resume from the next unread chapter;
- inspect engagement, pacing, clarity, emotional-impact, predictions, confusion, character reactions, favorite moment, keep-reading response, and craft notes for representative chapters;
- complete the manuscript and verify the final verdict contains audience/genre fit, strongest/weakest elements, character/pacing/plot/voice/ending feedback, unresolved confusion, fulfilled predictions, broken promises, top revisions, recommendation and score;
- edit a previously read chapter and confirm the historical chapter note is marked stale while remaining available as historical evidence;
- start a fresh reader after substantial revision and compare verdicts without deleting the prior run.

No Reader capability passes using a mocked model response in the final real-manuscript gate.

## Grammar Knowledge

- Confirm grammar sources are visible with authority, title, source URL, refresh cadence, last checked/success dates, status, and chunk count.
- Search for comma splice, sentence fragment, subject-verb agreement, pronoun agreement, passive voice, punctuation, and parallel structure.
- Confirm returned rules identify the source authority and link to the source.
- Run **Review current document grammar** against real fiction prose using a configured model.
- Confirm every returned issue cites only rule IDs supplied by the indexed knowledge base.
- Confirm the reviewer distinguishes a likely grammatical error from an intentional fragment/dialogue/voice choice when appropriate.
- Deliberately make a grammar error, re-run review, and confirm the issue is found with a source-grounded explanation and suggested repair.
- Confirm a model response citing a nonexistent rule ID is discarded rather than presented as sourced guidance.

## Publishing Knowledge

- Search and ask source-grounded questions about KDP eBook covers, KDP paperback covers, KDP print interiors, IngramSpark covers/interiors, Apple Books cover assets, and Kobo covers.
- Confirm answers expose the exact indexed excerpts used and preserve authority/source URL/checked date.
- Verify Ember does not claim a changing distributor rule is current when its indexed source is stale or failed.
- Manually refresh due sources and confirm changed source text replaces the prior live chunks transactionally.
- Simulate a failed source refresh and confirm the last successful or seeded rules remain searchable offline.
- Confirm refreshed source hashes and timestamps persist across restart.

## Scheduled Refresh

- Confirm the FastAPI lifespan starts the knowledge refresh scheduler.
- Confirm the scheduler checks only sources whose manifest refresh cadence is due.
- Confirm publishing sources may use a shorter cadence than stable grammar sources.
- Confirm an error is recorded against a failing source without terminating the EmberWriter service.
- Confirm the scheduler retries failed/due sources on a later interval.
- Confirm `EMBER_KNOWLEDGE_REFRESH_INTERVAL_SECONDS` and `EMBER_KNOWLEDGE_INITIAL_DELAY_SECONDS` can override scheduler timing for deployment/testing.

## Vector / Semantic Retrieval

Basic knowledge search must work without embeddings.

With a configured Ollama or OpenAI-compatible embedding model:

- index all current knowledge chunks;
- confirm vectors are stored by chunk ID, embedding model, dimensions, source-content hash, and creation time;
- edit/refresh a source and confirm changed chunks become eligible for re-embedding;
- re-index without `force` and confirm unchanged chunks are not embedded again;
- run a semantic query whose wording differs from the source terminology and confirm relevant rules can still surface;
- change embedding models and confirm vectors from the two models remain isolated;
- disable semantic search and confirm FTS/exact retrieval continues to work.

## Merge Gate

PR #8 is safe to merge only after the exact final head passes:

- all backend tests;
- Ruff;
- TypeScript compilation;
- production Vite build;
- no documented capability is knowingly stubbed.
