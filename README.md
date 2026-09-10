# EmberWriter

EmberWriter is a local-first AI fiction workspace built around durable manuscripts, structured story memory, continuity, and model choice. The manuscript is the source of truth: readable Markdown/JSON/YAML/text files live on your machine, while SQLite stores supplemental state such as snapshots and rebuildable narrative memory.

EmberWriter is model-agnostic. It supports Ollama directly and any OpenAI-compatible endpoint, including local servers such as LM Studio or vLLM.

## What exists in v0.2

- Three-pane authoring workspace: library, manuscript editor, and Ember AI panel.
- Local projects with manuscript, characters, world, relationships, timeline, scenes, style, and summaries folders.
- Human-readable story files instead of a proprietary document format.
- Autosave with automatic pre-save snapshots.
- Snapshot listing and restore API.
- Search across the local story library.
- Context compiler combining project settings, author style, summaries, active manuscript, selected text, relevant story files, and structured narrative memory.
- AI modes for Write, Continue, Rewrite, Brainstorm, Critic, and Continuity.
- Ollama and generic OpenAI-compatible model gateways.
- Model discovery from the configured model server.
- Import of an existing manuscript file or local story directory through the local API.
- Windows and macOS/Linux launch scripts.
- Narrative Memory Engine with source-aware canon, character state, character knowledge, relationships, timeline events, unresolved threads, locations, objects, and abilities.
- Automatic chapter/scene summaries and content-hash tracking so unchanged chapters are not repeatedly analyzed.
- Re-analysis replacement semantics: editing a chapter replaces memory derived from that source instead of accumulating stale duplicates.
- Ranked memory retrieval injected into generation and continuity checks ahead of ordinary text retrieval.
- Story Memory inspector with search, confidence, importance, source navigation, manual analysis, idle auto-analysis, and whole-manuscript memory building.
- Readable narrative-memory export at `summaries/narrative-memory.json` so derived state remains inspectable and rebuildable.

## Project format

A project is portable by design:

```text
EmberWriter/data/projects/my-novel/
├── project.json
├── manuscript/
│   └── chapter-001.md
├── characters/
├── world/
├── relationships/
├── timeline/
├── scenes/
├── style/
│   └── author-profile.md
├── summaries/
│   ├── rolling-summary.md
│   ├── unresolved-threads.md
│   └── narrative-memory.json
└── .ember/
    ├── story.db
    └── snapshots/
```

If the application disappears, the manuscript and story bible still exist as ordinary files. `.ember/story.db` is supplemental state, not the only copy of the work. Narrative memory can be rebuilt from the manuscript and is also exported to readable JSON.

## Requirements

- Python 3.11+
- Node.js 20+ (22 recommended)
- npm
- A model server if you want AI generation or automatic memory analysis

For Ollama, start Ollama normally and make sure at least one chat/instruct model is installed. EmberWriter defaults to `http://localhost:11434` and discovers installed models from the server.

For LM Studio, vLLM, or another compatible server, choose **OpenAI-compatible** in EmberWriter and enter the server's base URL and model ID.

## Windows quick start

From PowerShell in the repository root:

```powershell
./start.ps1
```

The script creates `backend/.venv`, installs the Python package, installs frontend dependencies when needed, starts both local services, and opens the UI.

- UI: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- FastAPI docs: `http://127.0.0.1:8000/docs`

## macOS / Linux quick start

```bash
chmod +x start.sh
./start.sh
```

Then open `http://127.0.0.1:5173`.

## Run manually

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Import an existing local story

The API can import either one supported text file or a directory. Directory imports preserve recognized EmberWriter folders; loose files are placed beneath `manuscript/`.

Example request:

```json
POST /api/projects/import
{
  "source_path": "C:/Writing/MyNovel",
  "name": "My Novel"
}
```

Supported source files are `.md`, `.txt`, `.json`, `.yaml`, and `.yml`. A native graphical folder picker is planned for the desktop packaging pass.

After importing a multi-chapter manuscript, select a model and use **Story memory → Build all**. EmberWriter analyzes chapters in manuscript order, skips files whose content hash is already current, and builds structured memory as it proceeds.

## Narrative Memory Engine

The model does not receive the entire library on every request. EmberWriter maintains a derived narrative state with atomic facts such as:

```text
[character_knowledge] Jax — knows — the vault key is beneath the chapel
[relationship] Sera — trusts — Jax with the vault-key secret
[object] vault key — held by — Elara
[thread] western gate prophecy — remains unresolved — true
```

Each fact keeps its source file, confidence, importance, and chapter order. Character knowledge is deliberately distinct from objective canon so the writer does not casually give one character information only another character learned.

When a manuscript file changes, its previous derived facts are replaced on re-analysis. The original manuscript remains authoritative if an extracted fact is ever wrong or stale.

The Story Memory panel lets you inspect what Ember believes it knows. **Analyze now** forcibly rebuilds the active manuscript file; **Build all** processes every manuscript file while skipping content that has not changed. **Auto memory** runs an idempotent analysis pass after a changed manuscript file has been saved and left idle.

Memory analysis sends the manuscript text to whichever model endpoint you configured. Keep Ollama/LM Studio/vLLM local if you want the entire workflow to remain on-device.

## Model and context flow

The frontend stores the configured model connection settings in browser local storage. The backend does not persist an API key supplied for an OpenAI-compatible endpoint.

```text
Author instruction
       +
Active manuscript / selection
       +
Project settings + author profile
       +
Recent analyzed chapter summaries
       +
Ranked structured narrative memory
       +
Relevant character/world/story files
       |
       v
Context Compiler
       |
       v
Model Gateway
       |
       +--> Ollama
       +--> OpenAI-compatible endpoint
```

Ordinary story-file retrieval is currently lexical. Structured memory adds a second retrieval layer ranked by query matches, continuity importance, confidence, and chapter order. Future retrieval work can add embeddings without changing the project or memory formats.

## Mature fiction behavior

EmberWriter is designed as an adult fiction tool rather than a general-purpose assistant. The generation layer tells compatible models not to sanitize consensual adult intimacy simply because it is explicit. The narrow baseline requires adults for erotic sexual content and does not treat requested non-consensual sexual abuse as erotic generation. This policy is centralized in `backend/app/generation.py` so product behavior can evolve without coupling it to storage or UI code.

## Development

Backend checks:

```bash
pip install -e './backend[dev]'
pytest backend/tests -q
ruff check backend/app backend/tests
```

Frontend checks:

```bash
cd frontend
npm install
npm run build
```

GitHub Actions runs both sets of checks on pull requests.

## Near-term roadmap

The next product layer is richer story orchestration on top of Narrative Memory: character dossiers, relationship/timeline views, Scene Architect, explicit setup/payoff tracking, snapshot/history UI, streaming generation, native import/recovery, project-level writing controls, document export, semantic retrieval, and native desktop packaging.
