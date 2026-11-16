# Stage 2 Chunk 15 — Local grounded answers and adversarial audit

Date: 2026-11-15
Status: **Engineering checkpoint, not literary quality certification**
Base: Stage 2 Chunk 14; stacked draft PR #158.

## Shipped in this checkpoint

- Explicit author-initiated Series Evidence Search "Ask from passages" local-model workflow. The backend calls only the fixed loopback Ollama HTTP endpoint with trust_env=false and no redirects; local proxy configurations may forward data, so no absolute no-egress guarantee is made.
- Balanced source-only retrieval across volumes, optional paired-book anchors, source IDs and immutable-index character offsets, and as-of-book cutoff. Missing evidence for an explicit comparison requires abstention.
- Conservative answer screening: model-proposed exact quotes must match retrieved passage text; unsupported substantive terms, tautologies, and vague answers cause abstention. A quote match is **not proof of semantic entailment**. All otherwise admissible drafts have status "review", semantic_entailment "unverified", and auto_approval_allowed false.
- UI shows retrieved passages, review status, evidence coordinates, exact-citation count, model limitations, and explicit no-auto-canon. In-flight UI search and model answers are invalidated and aborted if the series/book cutoff changes.
- Source, reviewer labels, and the user's private literary evaluation remain only on BarnesPC and are not committed.

## Independent audit and correction

An independent local code agent (HEAD 21ed7ab) found:
1. A **blocking fabricated claim** with an exact but irrelevant quotation could be displayed as a review candidate.
2. Comparative wording and "book 1 and 2" phrasing bypassed pairwise citation checks.
3. An in-flight result could reappear after changing the series or cutoff.
4. Model-name filtering alone cannot establish local-model provenance or absence of forwarding.

The first three issues were addressed with an extra fail-closed lexical support screen, broader explicit comparisons and two-book citation checks, plus frontend request invalidation/abort. The fourth is now disclosed accurately in the UI; actual network egress/proxy verification remains outstanding. These are syntactic and routing safeguards, not verified semantic understanding.

## Checkpoint verification

- Local Python 3.14: **282** selected backend tests passed, 629 deselected, one expected synthetic duplicate-mimetype warning.
- Targeted Ruff for changed backend files: passed.
- Frontend TypeScript/Vite production build: passed.
- Release scorecard: 4/4 tests passed; all 38 gates valid with **zero provisional 5/5 certifications**.
- Added adversarial regressions on the fabricated unrelated-quote answer, comparison wording, missing second-book citation, future-book cutoff, and positive grounded synthetic citation.
- GitHub CI status must be checked separately on the final PR commit.

## Unresolved gates

No independent expert literary approval, no 50 genuinely distinct human-reviewed cross-book holdout, no 80-volume load/concurrency benchmark for balanced retrieval, no independently verified source-to-claim entailment, and no trustworthy proof that an arbitrary local Ollama installation cannot proxy book text externally. The running private Series Vault's source files were not used in the hosted code audit or Git. No stable merge or release certification is authorized by this checkpoint.
