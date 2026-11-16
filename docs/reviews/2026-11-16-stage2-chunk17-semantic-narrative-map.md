# Stage 2 Chunk 17 — From literal retrieval toward series understanding

Status: **Draft engineering checkpoint, not certified literary comprehension**
Base: Stage 2 Chunk 16 contextual reasoning (PR #164).
Date: November 16, 2026.

## User problem

The 80-volume reference library was searchable, but source passages were not a durable, cross-book understanding of entities, relationships, beliefs, causes and reader knowledge. Existing Chunk 16 author-feedback-assisted trial delivered **8/26 provisional answers**, with no independent assessment of accuracy. The earlier baseline had 26/26 abstentions. No benchmark improvements should be inferred from this checkpoint without a new human review.

## New implementation

- Local semantic retrieval: partial, incremental source-exact window cache under the vault; local Ollama embedding endpoint (never remote by default) with cutoff filtering, per-source hash, multiple book diversity, and deterministic lexical fallback. This is a **bounded cache of encountered windows, not a full 80-volume semantic index**; the current scan cap is 2,000 cached windows.
- Availability handling: a failed local embedding call triggers a short cooldown to prevent 80-book source searches becoming repeated 10-second timeouts. The app continues with source-exact lexical retrieval and never represents cosine similarity as factual entailment.
- Persistent narrative mapping: author-invoked single-window extraction of candidate entities, relations, events, states, aliases, and explicit causal links. Scope (narrator vs character knowledge), optional knower, story time, reading book, source hash, offset and exact quote are separate fields. Strict model JSON schema, no automatic canon approval, resumable per-source progress with concurrent-update guard.
- Author-facing review UI in Series Evidence Search: choose a book/source and local model, start or resume, analyze one passage, inspect source-verified candidate claims and exact quotes, confirm only for research or reject, with progress and safe no-auto-canon warnings.
- Research context: only **explicitly author-confirmed, snapshot-verifiable, book-cutoff-safe** narrative claims may assist subsequent local contextual analysis. They remain labeled hypotheses, never primary evidence or independent verification.
- Privacy: raw manuscripts, local model prompts and any unredacted answer traces stay on BarnesPC; only synthetic unit tests and generic code enter Git. No source excerpts are committed. The fixed Ollama loopback endpoint does not itself prove a model/proxy cannot forward data.

## Verification

- Synthetic integration/targeted regression: 25 passed before adding strict extraction-schema regression; 18 passed in extraction-schema targeted run. Final full backend suite (run before last schema wording change) **934 passed, 2 skipped** on Windows with one synthetic ZIP duplicate-mimetype warning.
- Frontend TypeScript + Vite production build passed on Windows.
- Real private 80-volume vault API smoke: map reading HTTP 200, cloud model rejected HTTP 400, job creation HTTP 201, job progress HTTP 200, local readiness HTTP 200.
- Real extraction trial with book-1 source: first local Ollama invocation timed out after 90 seconds, 0 model-extracted claims. At the time the host GPU had an 8-GB VRAM ceiling and a distinct Ollama model with 24,576 context shown in 'Stopping...' state, consuming GPU. Even a short synthetic local-generation probe timed out. No live book-comprehension success claim is justified.
- Independent pass/fail author grading is absent for this new version.

## External public background versus primary manuscripts

Public guides such as https://destroyerwiki.com/world/ and https://destroyerwiki.com/entities/cure/ organize roles, aliases, book appearances, institutions and chronology. Those guides demonstrate a useful domain schema, **not** authoritative proof that any novel's specific passage entails a proposed assertion. Any future opt-in public reference source must have separate provenance and cannot be silently treated as primary manuscript evidence.

## Still blocking real comprehension

- The 80 books have **not** been fully mapped. There is no validated relationship graph / entity resolution across all books, complete chronology, plot causal model, character belief state or narrative arc inference. The current map stores candidate assertions and a source-order timeline.
- The 8/26 provisional coverage comes from feedback-assisted prior questions, not a blind author-verified 50-question holdout. Nothing here proves factual correctness.
- Model availability/latency and GPU contention currently prevent live source understanding. Do not kill another model's in-flight work or silently substitute a hosted model; resolve local contention explicitly before a new real-corpus run.
- Embedding cache is partial and requires actual local embedding success; no full-book throughput or retrieval-relevance benchmark is established.
- Claim-to-quote semantic entailment remains unverified and requires human author review before promotion.

No 5/5 score, no release merge, and no third-party expert signoff.
