# Stage 2 Chunk 16 — Source-linked contextual reasoning and human-reviewed memory

Status: **Draft engineering checkpoint; NOT a claim of 5/5 literary comprehension**
Base: Chunk 15 commit `6fbb01e`.

## Problem demonstrated by the author

The live 80-volume Destroyer Series Vault held 80 sources and five entity names, but **zero approved assertions**. The previous model prompt demanded a complete answer and exact source quotes in one response, while a strict token-overlap check rejected paraphrase. The real corpus assessment returned 26/26 abstentions. The author's review marked 25 incorrect, one partly correct as answers-to-the-question (not independent expert validation).

## Implemented in this chunk

1. **Contextual interpretation** in `series_context_answer.py`, invoked by the current POST `/api/series/{series_id}/grounded-answer` when the author explicitly chooses a local model. The offline no-model retrieval path stays intact. Source windows are selected across query variants and book periods, with earlier/later reading windows for explicit comparisons.
2. **Model-managed evidence references**, not exact copied quotes. The local model synthesizes a short narrative and chooses passage IDs; the backend checks passage ID bounds, retrieves source snapshots, verifies source-exact character offsets, and creates immutable source links. An independent citation-selection step prevents quoted-text format failures.
3. **Second, explicitly non-independent local verification pass.** If the model cannot support its own answer from selected passages, the service abstains with a named reason. Successfully screened answers are labeled **provisional**, never confirmed, with semantic entailment `unverified`. No model can approve canon.
4. **Durable semantic candidate memory** with pending-author-review status and book/source coordinates. A separate `series_context_memory.py` exposes read/review endpoints; only a human can mark a note `confirmed_for_research` or `rejected`. This is still not the approved Series Canon. Future answers can consult only confirmed research notes whose book cutoff is <= the question's cutoff, while still requiring fresh primary citations.
5. **Author feedback as private retrieval guidance only.** Twenty-six correction topics remain on BarnesPC in `author-guidance-<series-id>.json`. They can influence what manuscript text is searched but do not count as source evidence, independent ground truth, or evaluated accuracy.
6. **Frontend review controls** show actual cited passages separately from broad retrieved passages, link exact source positions, show model uncertainty, and permit explicit research-note review without canon approval. UI can target a separate local test API via `VITE_API_BASE_URL`.

## Private, real-corpus observations

The frozen 26-question author-challenged set was rerun on BarnesPC with local `llama3.2:3b`, not a blind evaluation. Previous pipeline: 0/26 provisional; this contextual pipeline with author-feedback-guided retrieval: **8/26 provisional, 18/26 abstentions** (6/22 new and 2/4 regression provisional). This is answer coverage only. Those eight answers have not been accepted as factually correct by the author, and a local verifier is not independent validation. Rerunning the same already-reviewed questions after feedback does not create 26 new holdout examples.

Observed on a separate local preview backend (port 8016): source retrieval and contextual-proposal listing both succeeded, and the corresponding frontend preview responded on port 5186. At least one live model request timed out after 38 seconds amid local Ollama contention. A test of `ornith:9b` also timed out; no model upgrade has been certified.

## Remaining blocking gaps

- Full text across 80 novels has **not** been converted into independently verified story facts or a complete temporal/epistemic graph. A source-linked candidate is not a demonstrated deep understanding.
- Large-range event causality, changing relationships, intentional character beliefs, and revelation timing remain under-tested.
- 8 provisional results need author scrutiny; model self-verification may still accept unsupported claims. Source exactness is necessary but not sufficient for semantic entailment.
- The query expansion based on prior corrections contaminates a blind assessment, and external public canon has not been reconciled with primary text.
- 80-book semantic-index scalability and Ollama concurrency/memory/latency require measurement; loopback transport does not guarantee that a configured local proxy cannot forward prompts.
- No independent expert certification, no 50 independently scored narrative questions, and no stable release merge.

## Security and provenance

The novels, primary excerpts, model inputs, unredacted outputs, human corrections and stored contextual cards remain exclusively on BarnesPC. None belong in GitHub or hosted AI prompt content. Author feedback is stored as private local hypotheses and separated from the frozen test inventory. Evidence exists with exact source IDs, book positions and character spans; those do not prove truth without review.
