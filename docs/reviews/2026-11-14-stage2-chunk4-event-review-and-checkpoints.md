# Stage 2 · Chunk 4: Reviewable Story Evidence (2026-11-14)

## Delivered and directly verified on BarnesPC

**Isolation:** Changes live in `EmberWriter-Stage2-Chunk3-Visible`, branch `feature/stage2-chunk3-visible`, with the real local app on `http://127.0.0.1:5173`. The primary repo's uncommitted work was not touched. Private story snapshots remain on BarnesPC and are never added to Git.

### Source research and human canon review

* `GET /api/series/{series}/event-leads` scans preserved source text for exact quoted language involving named entities and temporal/narrative cues, with per-book and series scopes and pages. Source fingerprints, positions and optional verified EPUB structural labels are retained.
* The scanner's purpose is a **search/review lead**, not a scene classifier, causal graph or trusted event history. It cannot reliably distinguish figurative language, dreams, POV, rumor, actual event time or narrator reliability. It neither creates nor approves story facts.
* The Destroyer 80-source corpus was scanned on the active backend: **640 unapproved literal leads spanning 80 source snapshots**, with up to eight per source in the series overview. The per-book view shows up to thirty candidates. These figures reflect configured limits, **not exhaustive extraction** of every scene/event. A verified quote can be displayed alongside the original surrounding passage.
* The new author event-review ledger supports staging an exact cited lead, marking it as `proposed`, explicitly classifying it (observed event, memory, dream, rumor, hypothetical), assigning book-sequence/flashback/flashforward/unknown chronology, recording notes and choosing approve or reject. Approval requires a human-entered event title and interpretation. A separate approved event ledger is not a claim in the generic Canon Graph.
* Three real source leads were staged on BarnesPC (from Books 1, 40 and 80). **All remain proposed, with zero approved.** No real quotes are in the repo.
* Story History displays this event discovery/approval UI directly, whether or not other approved facts are present; Discover also exposes it.

### Multi-source model-assisted extraction

* The local SQLite `series_extraction_batches` checkpoint table persists up to 80 selected source snapshots per batch, local Ollama model, source cursor, progress, and pause/cancel/error state. `POST /next` advances **one bounded up-to-1,400-character window** and recovers the existing per-source checkpoint when re-entered. An author can run one window or three at a time from the frontend, and pause/resume/cancel without silently promoting candidates.
* Both the per-source job and the batch release their leases on cancellation. Source fingerprints and series IDs are checked before work. No manuscript or generic canon updates occur.
* An 80-source batch was created for the real Destroyer library. A GPU-contention attempt returned a local model timeout without losing the checkpoint. It resumed successfully through dedicated CPU-only Ollama on `127.0.0.1:11435`, completing its **first** source window in 9.8 s and retaining its zero-candidate result. **This is not a finished 80-book model extraction.** The batch remains ready for further author-initiated work.
* `EMBER_STORY_OLLAMA_URL` can select only `127.0.0.1:11434` or `127.0.0.1:11435`. The Stage 2 launch script bootstraps the latter CPU-only server if absent. Neither path sends source text to cloud providers.

### Model quality and hardware observations

* The story evidence synthetic battery expanded from five to **ten predeclared cases**, including knowledge cutoffs, flashback order, later-book revelations, false narrations, setup/payoff, and unsupported claims. This is a narrow citation/evidence evaluation and **does not certify novel-quality scene writing or 80-book reasoning**.
* Local `llama3.2:3b` scored **8/10** in one real run (a quote attribution and a flashback-order miss). A first 8B attempt was **0/10** under severe GPU contention; those failures should not be interpreted as an intrinsic capability comparison. The independent GPU model bakeoff was consuming ~93% GPU during the attempt. A CPU-only test generated a correct synthetic fact-and-quote response in 5.27 s without borrowing the GPU.
* The user authorized stopping competing bakeoffs. Several were stopped and Ollama was restarted. Other bakeoff workers subsequently reappeared, so no performance claim should assume a permanently idle GPU. The second 8B ten-case run completed at **3/10 in 186.3 s**, still below the smaller 3B model's 8/10; none passes a full ten-case quality gate.

### Portable recovery

* Series Vault ZIP backups now carry original source-checksum-bound EPUB structural indexes and authored event review records with status, interpretation and citation. Restoration remaps source IDs, checks exact source quotations and section coordinates, and rejects tampering **before** creating an independent series.
* A private 80-book backup was actually generated, inspected, and deleted: **80 sources, 80 structural indexes, 3 unapproved event reviews, 8.43 MB ZIP, 2.28 s**. This tested backup creation and metadata integrity, not restoring a duplicated 80-book series. Two synthetic archive-restore roundtrips and adversarial tampering checks passed.
* Old version-one archives without these optional fields remain restorable. Local-only model extraction checkpoints are deliberately **not** portable to a newly remapped source namespace. To move these, add a separate explicitly designed checkpoint migration later; never copy old source IDs blindly.

### Verification and release standard

* **170 Series tests passed** (one expected malicious-EPUB ZIP warning); source quote, review, isolation, cancellation, compatibility, recovery and portability tampering all covered. The TypeScript/Vite production build, live Chrome browser navigation smoke and **4 release-scorecard tests** passed. The catalog still lists all 38 author gates. The 38-gate author release catalog remains valid with **zero** independently certified 5/5 domains.
* A correct final publication requires real book-wide scene extraction, author-approved continuity gold cases, long-term throughput evaluation, full app/security/accessibility checks, and human literary review. **Do not represent this work as all 38 gates passed or a fully completed 80-book narrative model.**

## Author workflow

In the live app: **Series → Explore → Story history** to inspect exact source leads and stage them for explicit event approval. **Series → Discover** has the same event research panel. **Series → Verify → extraction workbench → Durable multi-book extraction queue** shows the persisted 80-book batch and allows small, bounded steps. **Model Lab** runs the expanded ten-case synthetic evidence diagnostic. For portability, use the existing Series Vault backup/restore controls.

Keep author review in the loop. A quote is a citation, not automatically reliable narrative truth; a model output is a suggestion, not canon.
