# EmberWriter

EmberWriter is a local-first fiction authoring studio that combines manuscript organization, rich editing, durable version control, publishing/compile workflows, structured story intelligence, scene planning, author voice, relationship state, editorial analysis, AI readers, cover production, and model-agnostic AI writing.

The design rule is simple: **your manuscript is the source of truth**. Ordinary readable project files live on your machine. SQLite accelerates revision history, Story Intelligence, editorial analysis, reader history, and trusted reference retrieval, but the application does not trap the novel inside a proprietary database.

EmberWriter supports Ollama directly and generic OpenAI-compatible endpoints such as LM Studio, vLLM, and compatible hosted gateways.

## Implemented through v0.9

### Authoring workspace

- Binder-style project hierarchy with stable node IDs independent of filenames.
- Draft, Research, Story Bible, and reversible Trash roots.
- Nested folders/documents, stable ordering, metadata, compile inclusion, collections, targets, and missing-source detection.
- Corkboard cards backed by the same Binder nodes and order.
- Outliner backed by the same Binder nodes and metadata.
- Rich TipTap manuscript editor with undo/redo, headings, bold, italic, underline, strike, highlight, lists, block quotes, scene breaks, left/center/right alignment, spellcheck surface, selected-text operations, and word count.
- Rich editing round-trips to portable Markdown/HTML-compatible source rather than storing proprietary editor HTML as the only manuscript copy.
- Autosave plus explicit Save.

### Import and ingest

The application can import authentic writing material through the UI as a whole novel, novel portion, idea/note, or research item.

Supported upload formats:

- DOCX
- PDF
- EPUB
- RTF
- Markdown
- TXT
- HTML

Pasted text is also supported. DOCX import preserves the supported inline formatting/alignment set. EPUB import follows the book spine order. Whole-novel import detects chapter/prologue/epilogue/interlude/part boundaries and creates real Binder documents. Imported documents receive baseline revisions immediately.

The local-directory import API remains available for portable EmberWriter folders and text-based writing directories.

### Durable version control

EmberWriter has multiple recovery layers:

1. automatic pre-save filesystem snapshots;
2. SQLite document revision history;
3. named whole-project checkpoints.

Each distinct document revision stores a stable ID, parent revision, timestamp, source, note, SHA-256 content hash, word count, and complete recoverable content. You can compare an older revision to the current document, restore it, and later restore the version you disliked less; restoration never deletes the later history.

Whole-project checkpoints capture the author-owned text/project state, including Binder organization and editable project files. Project restore automatically creates a pre-restore safety checkpoint first, so the rollback itself can be undone. Binary cover artwork lives as ordinary project-local files under `assets/covers/`; those image files should be included in normal filesystem/project backups because the current text checkpoint store does not duplicate binary assets.

Derived Story Memory is checked against current manuscript hashes before generation and Story Intelligence operations. Facts extracted from a changed or deleted manuscript source are invalidated instead of surviving as stale AI context.

### Interior compile and publishing

Compile order comes from the Binder, not filesystem naming. Documents with Compile disabled are excluded.

EmberWriter generates:

- **DOCX** for editorial/submission workflows;
- **EPUB** for reflowable ebook distribution;
- **PDF** for print-oriented book interiors.

Publishing supports book title, author/pen name, language, EPUB TOC, and print trim dimensions. DOCX exports carry document metadata and preserve the supported rich formatting set. EPUB keeps reflowable HTML and navigation structure. PDF output honors the selected trim size, keeps representative inline formatting/alignment, and includes pagination.

Generated files are written beneath the project `exports/` directory and are downloadable from the app.

### Cover Studio

v0.9 adds a separate cover-production project that persists as readable JSON at `publishing/cover-profile.json` and stores uploaded artwork beneath `assets/covers/`.

Current output targets:

- **KDP Paperback** — calculates full-wrap width, spine, front/back positions, bleed, and type-safe guidance from the selected final page count and paper/interior type.
- **KDP eBook** — validates raster dimensions/ratio and produces an upload JPEG plus lossless PNG proof.
- **IngramSpark / official template** — deliberately requires the spine width from the exact IngramSpark product template instead of pretending one universal spine formula applies to every binding/paper combination.
- **Custom Print** — accepts author/publisher-supplied trim, bleed, and spine measurements.

The Cover Studio provides a live front/spine/back preview with optional guides and controls for title, subtitle, author/pen name, back blurb, imprint, ISBN, typography, alignment, colors, artwork placement/opacity, and barcode handling. Uploaded PNG/JPEG/TIFF/WebP assets are validated as real images and kept inside the story project.

Cover preflight checks include page-count constraints, spine-text eligibility, missing artwork/barcode assets, effective print-art resolution, KDP ebook minimum/maximum dimensions and aspect guidance, Ingram template-spine requirements, and common back-cover density issues.

Print output is a single-page full-wrap PDF at the calculated/requested physical dimensions. That geometry validation is **not a claim of final distributor approval**. Before publishing, run the PDF through the target distributor's current preview/preflight to verify platform-specific font embedding, transparency, color-space, barcode, and placement requirements. EmberWriter's trusted publishing knowledge base keeps the current authority links available because those rules can change.

### Editorial Studio

v0.8 adds deterministic manuscript diagnostics with persisted, source-linked findings. Reports can run against the current document or the whole Binder Draft.

Current report catalog:

- Repeated Words
- Repeated Phrases
- Adverbs
- Filler Words
- Filter Words
- Passive Voice
- Weak Verb Clusters
- Sentence Length
- Paragraph Length
- Repeated Sentence Starts
- Sticky Sentences
- Redundancies
- Cliches
- Dialogue Adverbs
- Dialogue Balance
- Readability
- Punctuation Emphasis

Each finding stores the stable Binder node ID when available, source path/hash, line and source offsets, excerpt/anchor, severity, explanation, and suggested review action. Findings and runs persist in SQLite. Authors can resolve, ignore, or reopen findings. When source prose changes, historical findings are marked stale rather than silently attaching themselves to different text.

Project editorial thresholds are portable in `style/editorial-profile.json`, and finding navigation opens the correct Binder document and selects the current flagged prose where possible.

### AI Reader Panel

EmberWriter can run persistent manuscript reads from three distinct perspectives:

- **Genre Fan** — emotional engagement, chemistry, favorite moments, anticipation, promises/payoffs, and whether the reader wants to keep going.
- **Casual Reader** — clarity, pacing drag, confusion, character tracking, accessibility, and where an ordinary reader may disengage.
- **Strong Editor** — causality, scene purpose, structure, character arcs, POV, pacing, genre delivery, setup/payoff, and high-leverage revisions.

A Reader run consumes the Draft in Binder order one document at a time. Each chapter reaction is stored before Ember moves to the next chapter, and predictions/confusion from earlier chapters are carried forward so later reactions are informed by the reader's accumulated experience rather than a one-shot summary.

Runs can be interrupted and resumed after restart. Completed runs synthesize a whole-book verdict covering score, audience and genre fit, strengths/weaknesses, character/pacing/plot/voice/ending feedback, unresolved confusion, fulfilled predictions, broken promises, top revisions, and recommendation. Historical chapter notes become visibly stale if their source chapter changes.

### Trusted grammar and publishing knowledge

v0.8 adds a separate global `data/knowledge.db` reference store. It is source-attributed and independently rebuildable from the source manifest and packaged fallback rules.

The initial authority set includes university writing-center material for grammar and official/current publishing documentation from Amazon KDP, IngramSpark, Apple Books, and Kobo Writing Life.

Knowledge records retain authority/source title, source URL, category, refresh cadence, last checked/last successful refresh time, source/chunk hashes, refresh error state, and indexed chunks.

On startup EmberWriter seeds a last-known-good local rule set and runs a scheduled refresh loop. Only sources due under their configured cadence are checked. A failed network refresh records the error but does **not** erase the last good rules, so reference search remains useful offline.

Search works without an embedding model through SQLite/FTS retrieval. Authors can optionally configure an Ollama or OpenAI-compatible embedding model; vectors are stored per chunk, embedding model, dimension, and content hash, and only changed chunks require re-indexing.

**Grammar Review** gives the configured language model only retrieved trusted grammar rules as normative evidence and rejects issues that cite rule IDs not present in that evidence. It also instructs the reviewer to distinguish grammatical mistakes from intentional fiction fragments, dialogue, rhythm, and voice.

Publishing questions can be answered against retrieved trusted excerpts with the supporting rule IDs and authority/source details visible in the UI.

### Narrative Memory Engine

EmberWriter extracts rebuildable, source-aware story state from manuscript chapters:

- canon;
- character state;
- character-specific knowledge;
- relationships;
- timeline events;
- unresolved threads/setup/payoff state;
- locations;
- objects;
- abilities.

Each fact retains its source file, confidence, importance, and chapter order. Character knowledge is intentionally distinct from objective canon so one character does not automatically know what another learned.

The Story Memory panel supports inspection, filtering, per-chapter analysis, and whole-manuscript memory builds. Changed source files replace or invalidate their previous derived memory.

### Characters, relationships, and Story Intelligence

Character dossiers under `characters/` are combined with manuscript-derived state and knowledge. Generation detects known character names in the current request/selection/context and injects their dossiers plus current story state.

Relationship Intelligence preserves source-aware relationship history rather than reducing a relationship to a single score.

Relationship Chemistry stores pairing/group-specific information such as attraction language, verbal rhythm, trust, vulnerability, power dynamics, established milestones, lore/magic resonance, author notes, and meaningful next escalation. Author-owned boundaries and milestones cannot be silently overwritten by a new AI inference pass.

The Aftermath workflow proposes relationship/state changes from a completed scene and requires review before those changes are applied.

### Scene Architect

Scene Architect builds a structured plan from current canon, character knowledge, relationship history, chemistry, project voice, and craft settings.

Plans can include POV and participants, location, objective/conflict, opening state, causal beats, emotional arc, relationship movement, reveals, continuity guardrails, unresolved threads, intimacy/romance notes where relevant, ending state, and next-scene pressure.

Plans are persisted as ordinary JSON beneath `scenes/` and can be sent directly to Writer.

### Prose, voice, and intimacy craft

EmberWriter separates prose identity from explicitness.

**Voice Lab** analyzes a real prose sample and stores a reusable `style/voice-profile.json` describing sentence rhythm, diction, imagery, dialogue behavior, interiority, POV distance, sensual/romantic voice, signature traits, and avoidances. **Voice Lock** injects that compact profile into future writing.

The craft system separately controls heat (Simmer / Hot / Scorching / Inferno), tension curve (Slow Burn / Steady Rise / Pressure Cooker / Flashpoint), sensory intensity, dialogue intensity, interiority, and project prose rules/avoidances.

For consensual adult fiction, high heat can remain explicit and on-page when supported by the configured model. The writing pipeline still prioritizes character psychology, pacing, mutual agency, established voice, continuity, and aftermath rather than treating explicitness as a substitute for prose quality.

An optional **Craft Pass** performs a second model call as a fiction line editor, targeting repetitive cadence, generic filler, over-explanation, weak verbs, interchangeable dialogue, spatial confusion, incoherent metaphor, and mechanical intensity while preserving scene facts and requested tone.

### AI modes and model gateway

Current AI modes:

- Write
- Continue
- Rewrite
- Brainstorm
- Critic
- Continuity

The context pipeline can combine the active manuscript, selected text, project settings, author profile, Voice Lock, craft profile, recent chapter summaries, ranked Story Memory, detected character dossiers, character knowledge/state, relationship history, chemistry, and relevant story files.

Model providers:

- Ollama
- generic OpenAI-compatible endpoint

API keys supplied for an OpenAI-compatible endpoint are passed with the request and are not persisted by the backend.

## Project format

A project remains portable:

```text
data/
├── knowledge.db
└── projects/my-novel/
    ├── project.json
    ├── binder.json
    ├── manuscript/
    ├── characters/
    ├── world/
    ├── relationships/
    ├── timeline/
    ├── scenes/
    ├── research/
    ├── notes/
    ├── publishing/
    │   └── cover-profile.json
    ├── assets/
    │   └── covers/
    ├── style/
    │   ├── author-profile.md
    │   ├── craft-profile.json
    │   ├── editorial-profile.json
    │   └── voice-profile.json
    ├── summaries/
    │   ├── rolling-summary.md
    │   ├── unresolved-threads.md
    │   └── narrative-memory.json
    ├── exports/
    └── .ember/
        ├── story.db
        └── snapshots/
```

If EmberWriter disappears, the manuscript, story-bible material, cover configuration, and original uploaded cover assets remain ordinary files. Derived Narrative Memory and reference indexes can be rebuilt.

## Requirements

- Python 3.11+
- Node.js 22 recommended
- npm
- A compatible model server for AI generation/analysis
- Optional embedding model for semantic knowledge retrieval

## Windows quick start

From PowerShell in the repository root:

```powershell
./start.ps1
```

The launcher creates the Python environment when needed, installs dependencies, starts the local FastAPI service and Vite UI, and opens the application.

- UI: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## macOS / Linux quick start

```bash
chmod +x start.sh
./start.sh
```

## Manual development

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
pytest tests -q
ruff check app tests
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run dev
```

GitHub Actions runs backend tests, Ruff, and the production TypeScript/Vite build on pull requests.

Knowledge refresh scheduler defaults can be overridden for development/deployment with:

- `EMBER_KNOWLEDGE_INITIAL_DELAY_SECONDS`
- `EMBER_KNOWLEDGE_REFRESH_INTERVAL_SECONDS`

## Release acceptance standard

Unit tests are necessary but not sufficient. Before a release is treated as author-ready, EmberWriter is tested against a real author-owned manuscript and real representative cover artwork rather than generated filler.

The formal checklists are:

- `docs/REAL_MANUSCRIPT_ACCEPTANCE.md`
- `docs/EDITORIAL_READER_KNOWLEDGE_ACCEPTANCE.md`
- `docs/COVER_STUDIO_ACCEPTANCE.md`

The final dogfood gate requires real import, editing, deterministic editorial reports, actual configured-model Reader runs, source-backed grammar/publishing guidance, memory, character/relationship, Scene Architect, craft, revision, project rollback, recovery, interior compile, and DOCX/EPUB/PDF verification. Cover acceptance additionally checks real high-resolution artwork, correct final formatted page count/paper choice, visual safe zones, barcode clearance, exact exported dimensions, and the distributor's own preview/preflight. Export files must be reopened and inspected; a successful return code or matching file extension is not enough.

## Product direction

EmberWriter is being built as one integrated author studio rather than disconnected tools:

- Scrivener-class organization and project control;
- AutoCrit-class editorial analysis and reader feedback;
- Ember Story Intelligence and continuity;
- prose/voice/relationship/intimacy craft;
- trusted grammar/publishing reference knowledge;
- local-first ownership and model choice;
- professional compile, recovery, publishing, and commercial cover workflows.

v0.9 establishes distributor-aware cover geometry and deterministic editable layout. Future cover work can deepen design sophistication—custom embedded typography, template overlays, crop/position controls, stronger color/prepress tooling, and optional image-generation integrations—without flattening title/spine/back text into generated artwork.
