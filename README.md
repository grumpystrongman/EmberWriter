# EmberWriter

EmberWriter is a local-first fiction authoring studio that combines manuscript organization, rich editing, durable version control, publishing/compile workflows, structured story intelligence, scene planning, author voice, relationship state, and model-agnostic AI writing.

The design rule is simple: **your manuscript is the source of truth**. Ordinary readable project files live on your machine. SQLite accelerates revision history and Story Intelligence, but the application does not trap the novel inside a proprietary database.

EmberWriter supports Ollama directly and generic OpenAI-compatible endpoints such as LM Studio, vLLM, and compatible hosted gateways.

## Implemented in v0.7

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

The older local-directory import API remains available for portable EmberWriter folders and text-based writing directories.

### Durable version control

EmberWriter has multiple recovery layers:

1. automatic pre-save filesystem snapshots;
2. SQLite document revision history;
3. named whole-project checkpoints.

Each distinct document revision stores a stable ID, parent revision, timestamp, source, note, SHA-256 content hash, word count, and complete recoverable content. You can compare an older revision to the current document, restore it, and later restore the version you disliked less; restoration never deletes the later history.

Whole-project checkpoints capture the author-owned project state, including Binder organization and editable project files. Project restore automatically creates a pre-restore safety checkpoint first, so the rollback itself can be undone.

Derived Story Memory is checked against current manuscript hashes before generation and Story Intelligence operations. Facts extracted from a changed or deleted manuscript source are invalidated instead of surviving as stale AI context.

### Compile and publishing

Compile order comes from the Binder, not filesystem naming. Documents with Compile disabled are excluded.

EmberWriter currently generates:

- **DOCX** for editorial/submission workflows;
- **EPUB** for reflowable ebook distribution;
- **PDF** for print-oriented book interiors.

Publishing supports book title, author/pen name, language, EPUB TOC, and print trim dimensions. DOCX exports carry document metadata and preserve the supported rich formatting set. EPUB keeps reflowable HTML and navigation structure. PDF output honors the selected trim size, keeps representative inline formatting/alignment, and includes pagination.

Generated files are written beneath the project `exports/` directory and are downloadable from the app.

Distributor requirements can change. Final KDP/other-platform compatibility is verified against the current distributor documentation during release acceptance rather than treated as a permanent claim.

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

Plans can include:

- POV and participants;
- location;
- objective and conflict;
- opening state;
- causal beats;
- emotional arc;
- relationship movement;
- reveals;
- continuity guardrails;
- unresolved threads;
- intimacy/romance notes where relevant;
- ending state;
- next-scene pressure.

Plans are persisted as ordinary JSON beneath `scenes/` and can be sent directly to Writer.

### Prose, voice, and intimacy craft

EmberWriter separates prose identity from explicitness.

**Voice Lab** analyzes a real prose sample and stores a reusable `style/voice-profile.json` describing sentence rhythm, diction, imagery, dialogue behavior, interiority, POV distance, sensual/romantic voice, signature traits, and avoidances. **Voice Lock** injects that compact profile into future writing.

The craft system separately controls:

- heat: Simmer / Hot / Scorching / Inferno;
- tension curve: Slow Burn / Steady Rise / Pressure Cooker / Flashpoint;
- sensory intensity;
- dialogue intensity;
- interiority;
- project prose rules and avoidances.

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
data/projects/my-novel/
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
├── style/
│   ├── author-profile.md
│   ├── craft-profile.json
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

If EmberWriter disappears, the manuscript and story-bible files still exist as readable files. Derived Narrative Memory can be rebuilt from the manuscript.

## Requirements

- Python 3.11+
- Node.js 22 recommended
- npm
- A compatible model server for AI generation/analysis

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

## Release acceptance standard

Unit tests are necessary but not sufficient. Before a release is treated as author-ready, EmberWriter is tested against a real author-owned manuscript rather than generated filler.

The formal checklist lives at:

`docs/REAL_MANUSCRIPT_ACCEPTANCE.md`

That gate requires real import, editing, AI, memory, character/relationship, Scene Architect, craft, revision, project rollback, recovery, compile, and DOCX/EPUB/PDF verification. Export files must be reopened and inspected; a successful return code or matching file extension is not enough.

## Product direction

EmberWriter is being built as one integrated author studio rather than disconnected tools:

- Scrivener-class organization and project control;
- AutoCrit-class editorial analysis and manuscript diagnostics;
- Ember Story Intelligence and continuity;
- prose/voice/relationship/intimacy craft;
- local-first ownership and model choice;
- professional compile, recovery, and publishing workflows.

The next major track after the v0.7 authoring core is the editorial-analysis engine: manuscript-wide deterministic reports, issue navigation, genre/style benchmarking, and AI-assisted revision layered on top of the stable Binder/document identities already in place.
