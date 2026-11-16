# Chunk 4 — Local streaming reliability checkpoint

Date: November 13, 2026. Scope: author-invoked local diagnostic, not content extraction.

## Delivered

- A synthetic-only Ollama streaming probe with strict 45-second wall-clock cutoff, loopback endpoint, disabled HTTP environment proxies, bounded event/byte/text counts, and installed-local-model membership check.
- Reports elapsed wall time, first response text time, Ollama model load time, prompt evaluation duration, generation duration, prompt and generation tokens, and generation throughput where Ollama supplies valid metrics.
- A stream can only be marked **passed** if its end marker arrives and its parsed JSON cites the exact invented sentence and correct target. Incomplete streams, timeouts, invalid responses and incorrect answers remain unverified.
- Explicit UI controls for **Measure startup and streaming** and **Cancel**, exposed in **Series → Explore → Model Lab** and **Series → Knowledge Lab → Local AI readiness**.
- Browser disconnect watcher cancels the in-flight streaming coroutine. No source book text, source metadata or generated output is written to Series Vault.
- No automatic extraction queues are enabled based on this small check.

## Verification

- Synthetic unit tests include exact answer, incorrect answer, early stream termination, timeout, response bound, connection cancellation, and series/model access guards.
- Expanded focused backend regression: **28 passed**, including the new generation-throughput assertion.
- Ruff check, Git whitespace check and TypeScript/Vite production build: **passed**.
- Live browser CDP smoke confirmed streaming diagnostic visible and enabled in Model Lab, all other Stage 2 tabs, the 80-source reference set, 27 approved assertions in the separate fixture, and the original-EPUB control.
- Live rerun after backend restart gave `llama3.2:3b`: incorrect exact-answer result, ~5707 ms wall clock, ~5418 ms to first text, ~4448 ms model loading, 18 generated tokens, **51.6 tokens/sec**. No source text sent.
- Real Ollama `llama3.2:3b` gave two **incorrect** exact-answer results: run 1 total ~4998 ms / first text ~4605 ms / model load ~4121 ms; run 2 total ~626 ms / first text ~277 ms / model load ~13 ms. Both responses completed, but neither met the exact synthetic evidence requirement. No private book text was sent.

## Interpretation and remaining gates

The model can stream, and cold loading is a significant share of startup delay. This **does not mean the model is reliable for story extraction or chronology**. Do not auto-approve canon or turn on multi-book inference from transport timings.

Next stages of Chunk 4: evaluate a small set of candidate local models against independently graded fiction probes; preserve book/chapter provenance in bounded extraction; provide opt-in small batch scheduling with author checkpoints; run multi-book chronology and memory benchmarks before scaling.
