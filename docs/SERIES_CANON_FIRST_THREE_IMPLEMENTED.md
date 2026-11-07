# Series Vault, Canon Graph and Temporal Intelligence — first usable release

This is the **first working implementation** of the three professional-author features, on the stacked feature branch `feature/series-vault-canon-timeline` ([PR #125](https://github.com/grumpystrongman/EmberWriter/pull/125)). It is an **author review build**, not yet the general-availability release.

## Opening the feature

On the existing isolated Windows preview, open `http://127.0.0.1:5173` and choose **Series** in the top navigation. The desktop shortcut **EmberWriter Author Preview** opens the preview if it isn't already running. Data is local, stored separately at `%LOCALAPPDATA%\EmberWriter\AuthorPreviewData`; original author projects aren't migrated automatically.

### 1. Series Vault

- Create a series, set a description, and add volumes in book order.
- Link an existing EmberWriter project **read-only**, or import a file you own or may legally use. Supported: Markdown, plain TXT, DOCX, EPUB and **text-based** PDF. A scanned PDF must be converted to text separately. Single-import limit: 25 MB.
- Assign book/novella/short-story/companion/notes type and published/approved/draft/reference edition status. Modify these fields later without altering already established book chronology.
- Evidence is stored as immutable, SHA-256-checked **local snapshots**. If a linked project's text changes, the original evidence stays stable and is marked stale; re-import/new-edition workflow is intentionally explicit rather than silently replacing citations.
- Download a private series ZIP including texts, source locations, approved/proposed canon, and book structure. Restore creates a **new independent series** with remapped IDs, never overwriting the author's existing series or manuscript projects. Keep ZIP private: it contains the author's original manuscript text.
- Remove a mistakenly created vault using the secondary **Delete this series vault** action and an exact typed-title confirmation. Deletion removes its copied evidence and canon records, **never** any linked original book projects.

### 2. Canon Graph

- Establish typed entities (characters, artifacts, places, organizations, rules, events, species and concepts), with aliases.
- Choose an exact quote from an imported source passage. Propose a fact such as `Moon Key — located_in — glass vault`, including source offsets, book and status.
- Distinguish three *separate* knowledge classes: **world truth**, **what a particular character believes**, and **what readers have been told**.
- **Nothing is canonical until the author explicitly selects Approve as canon.** The original quoted evidence is immutable, and approved facts are not silently rewritten. Contradictory approved facts are flagged, not automatically resolved.
- Optional local Ollama can suggest candidate facts **only when invoked** and only from a selected excerpt. Model suggestions must quote exactly and reference known entities, and remain **unsaved** until the author fills/reviews the proposal and explicitly approves it. AI does not get permission to change the story.

### 3. Temporal Intelligence

- Select Book 1, Book 2 or another point in the series; optionally choose a scene sequence within the book.
- Select **established world truth**, **character belief** or **reader reveal**. For character beliefs, select the particular character.
- Ask a question like “Where is the Moon Key?” The current deterministic research engine resolves known entities and returns **author-approved cited facts** that are valid by the selected book/scene. It does **not** scan the entire prose at query time or invent answers from a generative model.
- Later books' sources cannot leak into earlier as-of queries. The same artifact can be in the glass vault in Book 1 and the sunlit tower in Book 2, with the correct answer changing by book. Unsupported or ambiguous questions are surfaced rather than guessed.
- Read a full timeline of facts with exact supporting passage, source document, book and offset. Competing approved fact values are flagged for author review.

## Engineering proof

- A new SQLite series database stays separate from existing project `story.db` files.
- Local snapshots are checksummed; any altered source evidence fails integrity validation.
- Portable backups are validated for duplicates, unexpected ZIP paths, content digests and limits before any new series is created.
- Exact quote matching, status transitions, chronology and author consent are enforced in backend APIs, not merely by UI text.
- The series is browsable even when no individual book project is selected.
- TypeScript/Vite build and focused backend tests passed; full CI and headless browser workflow are run before acceptance.
- Headless Edge verified this exact chain on synthetic manuscripts: create series → import two books → create Moon Key entity → approve separate location facts for Book 1/Book 2 → ask as of Book 1 without leaking Book 2 → ask as of Book 2 → download ZIP → restore a new series → inspect mobile-width layout (390 px). **PASS**, with no relevant resource errors after fixing a stale source-selection race. The isolated demo has been tidied to a single **Demo - The Lantern Cycle (synthetic)** series with two sample books and approved source-backed facts.

## Limits and next stage

This first release does not imply universal semantic understanding of every fictional universe. It currently uses **author-curated entities and approved source evidence** and deterministic retrieval. Automated full-volume fact extraction, richer relationship visualizations, scalable entity alignment, deep contradiction detection, semantic search, timeline calendar conversion, editors' collaboration and robust retcon workflows are future milestones.

Supported “as-of” times are **book order and optional within-book sequence**, not absolute in-world dates yet. If world truth applies before its first textual mention, the author currently needs to model it from the earliest available anchored source book and avoid projecting it into earlier books without evidence.

Before promising large career-series performance, benchmark on a synthetic 12-book corpus with thousands of cited facts, human-reviewed extraction quality, intentional narrator misdirection, and an author acceptance pass. Keep all real novelist manuscript ingestion explicitly rights-authorized.

**Author-first rule:** Data, canon and creative decisions remain the author's. Optional model assistance is evidence-only and never automatically publishes, promotes, retcons or rewrites.
