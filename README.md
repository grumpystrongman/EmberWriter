# EmberWriter

EmberWriter is a local-first AI fiction workspace built around durable manuscripts, story memory, continuity, and model choice. The manuscript is the source of truth: readable Markdown/JSON/YAML/text files live on your machine, while SQLite stores derived state such as snapshots and future narrative-memory data.

The first MVP is intentionally model-agnostic. It supports Ollama directly and any OpenAI-compatible local endpoint, including servers such as LM Studio or vLLM.

## What exists in the MVP

- Three-pane authoring workspace: library, manuscript editor, and Ember AI panel.
- Local projects with manuscript, characters, world, relationships, timeline, scenes, style, and summaries folders.
- Human-readable story files instead of a proprietary document format.
- Autosave with automatic pre-save snapshots.
- Snapshot listing and restore API.
- Search across the local story library.
- Context compiler that combines project settings, author style, rolling summary, unresolved threads, active manuscript, selected text, and relevant story files.
- AI modes for Write, Continue, Rewrite, Brainstorm, Critic, and Continuity.
- Ollama and generic OpenAI-compatible model gateways.
- Model discovery from the configured local server.
- Import of an existing manuscript file or local story directory through the local API.
- Windows and macOS/Linux launch scripts.

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
│   └── unresolved-threads.md
└── .ember/
    ├── story.db
    └── snapshots/
```

If the application disappears, the manuscript and story bible still exist as ordinary files. `.ember/story.db` is supplemental state, not the only copy of the work.

## Requirements

- Python 3.11+
- Node.js 20+ (22 recommended)
- npm
- A local model server if you want AI generation

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

The MVP API can import either one supported text file or a directory. Directory imports preserve recognized EmberWriter folders; loose files are placed beneath `manuscript/`.

Example request:

```json
POST /api/projects/import
{
  "source_path": "C:/Writing/MyNovel",
  "name": "My Novel"
}
```

Supported source files are `.md`, `.txt`, `.json`, `.yaml`, and `.yml`. A graphical folder picker is planned for the next UI pass.

## Model gateway

The frontend stores only the local model connection settings in browser local storage. The backend does not persist an API key supplied for an OpenAI-compatible endpoint.

Generation flow:

```text
Author instruction
       +
Active manuscript / selection
       +
Project settings + author profile
       +
Rolling summary + unresolved threads
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
       +--> OpenAI-compatible local server
```

The current retrieval implementation is lexical and deliberately simple. The architecture leaves room for embeddings, knowledge graphs, character-state extraction, relationship state, event timelines, and multi-pass canon analysis without changing the durable project format.

## Mature fiction behavior

EmberWriter is designed as an adult fiction tool rather than a general-purpose assistant. The generation layer tells compatible models not to sanitize consensual adult intimacy simply because it is explicit. The narrow baseline in the MVP requires adults for erotic sexual content and does not treat requested non-consensual sexual abuse as erotic generation. This policy is centralized in `backend/app/generation.py` so product behavior can evolve without coupling it to storage or UI code.

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

The next high-value work is the Narrative Memory Engine: automatic chapter summarization, canon extraction, character knowledge/state, relationship changes, unresolved setup/payoff tracking, timeline events, and context ranking. After that: richer editor commands, graphical import/recovery, snapshot browser, scene cards, project settings, streaming generation, document export, and native desktop packaging.
