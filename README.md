# EmberWriter

EmberWriter is a local-first AI fiction workspace built around durable manuscripts, structured story memory, character continuity, relationship state, scene planning, prose craft, author voice, and model choice. The manuscript is the source of truth: readable Markdown/JSON/YAML/text files live on your machine, while SQLite stores supplemental state such as snapshots and rebuildable narrative memory.

EmberWriter is model-agnostic. It supports Ollama directly and any OpenAI-compatible endpoint, including local servers such as LM Studio or vLLM.

## What exists in v0.4

- Three-pane authoring workspace: library, manuscript editor, and Ember AI panel.
- Local projects with manuscript, characters, world, relationships, timeline, scenes, style, and summaries folders.
- Human-readable story files instead of a proprietary document format.
- Autosave with automatic pre-save snapshots.
- Snapshot listing and restore API.
- Search across the local story library.
- Context compiler combining project settings, author style, summaries, active manuscript, selected text, relevant story files, structured narrative memory, and participant-specific character intelligence.
- AI modes for Write, Continue, Rewrite, Brainstorm, Critic, and Continuity.
- Ollama and generic OpenAI-compatible model gateways with local model discovery.
- Import of an existing manuscript file or local story directory through the local API.
- Windows and macOS/Linux launch scripts.
- Narrative Memory Engine with source-aware canon, character state, character knowledge, relationships, timeline events, unresolved threads, locations, objects, and abilities.
- Automatic chapter/scene summaries and content-hash tracking so unchanged chapters are not repeatedly analyzed.
- Story Intelligence layer that turns raw memory into per-character state, per-character knowledge, dossier links, and relationship edges.
- Scene Architect for POV, participants, location, objective, conflict, causal beats, emotional movement, relationship changes, reveals, continuity guardrails, unresolved threads, intimacy notes, ending state, and next-scene pressure.
- Prose & Intimacy Craft Engine with project heat levels, tension curves, sensory/dialogue/interiority controls, Voice Lock, Voice Lab, and an optional second Craft Pass.
- Deterministic character-dossier injection when known characters appear in the current request or scene context.
- Readable craft and voice profiles stored under `style/` so the writing system remains portable and inspectable.

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
│   └── scene-plan-xxxxxxxxxx.json
├── style/
│   ├── author-profile.md
│   ├── craft-profile.json
│   └── voice-profile.json
├── summaries/
│   ├── rolling-summary.md
│   ├── unresolved-threads.md
│   └── narrative-memory.json
└── .ember/
    ├── story.db
    └── snapshots/
```

If the application disappears, the manuscript and story bible still exist as ordinary files. `.ember/story.db` is supplemental state, not the only copy of the work. Narrative memory can be rebuilt from the manuscript. Craft and voice profiles are ordinary JSON files that can be edited or backed up with the book.

## Requirements

- Python 3.11+
- Node.js 20+ (22 recommended)
- npm
- A model server if you want AI generation, automatic memory analysis, Voice Lab, Craft Pass, or Scene Architect

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
[relationship] Sera — trusts — Jax
[object] vault key — held by — Elara
[thread] western gate prophecy — remains unresolved — true
```

Each fact keeps its source file, confidence, importance, and chapter order. Character knowledge is deliberately distinct from objective canon so the writer does not casually give one character information only another character learned.

When a manuscript file changes, its previous derived facts are replaced on re-analysis. The original manuscript remains authoritative if an extracted fact is ever wrong or stale.

The Story Memory panel lets you inspect what Ember believes it knows. **Analyze now** forcibly rebuilds the active manuscript file; **Build all** processes every manuscript file while skipping content that has not changed. **Auto memory** runs an idempotent analysis pass after a changed manuscript file has been saved and left idle.

Memory analysis sends manuscript text to whichever model endpoint you configured. Keep Ollama/LM Studio/vLLM local if you want the entire workflow to remain on-device.

## Characters and relationships

The Story Intelligence endpoint derives author-friendly views from the lower-level memory store. Character dossiers under `characters/` are combined with extracted character state and knowledge. The UI shows what a character currently knows separately from objective story facts, which is important for mysteries, secrets, betrayals, reveals, and multi-POV books.

When generation detects a known character name in the author request, selected text, or active scene context, EmberWriter deterministically injects that character's dossier plus their current state, knowledge, and relationship history. This is designed to make dialogue, reactions, flirtation, conflict, and intimacy character-specific instead of relying on generic model defaults.

Relationship facts are exposed as source-aware edges. EmberWriter keeps the history instead of collapsing every relationship into one score: a later scene can therefore reason about how trust, attraction, conflict, loyalty, fear, or intimacy changed and where that change was established.

## Scene Architect

Scene Architect is a planning pass before prose generation. It uses the active manuscript, relevant structured memory, participant-specific knowledge/state, relationship history, project craft profile, book voice, and the author's request to create a JSON scene plan.

A plan includes:

```text
POV + participants + location
scene objective + conflict
opening state
causal scene beats
emotional arc
relationship movement
reveals
continuity guardrails
threads in play
intimacy/romance notes when relevant
ending state
next-scene pressure
```

Generated plans are saved to `scenes/scene-plan-*.json`. **Send to Writer** converts the plan into a structured prose prompt so the normal Writer can execute the planned scene while the context compiler still supplies canon, character intelligence, craft direction, and memory.

## Prose & Intimacy Craft Engine

The craft engine exists because increasing explicitness is not the same thing as improving a scene. EmberWriter separates **heat**, **tension shape**, and **voice** so the author can control each independently.

### Heat

- **Simmer** — attraction, anticipation, proximity, restraint, subtext, and interrupted choices.
- **Hot** — unmistakable sustained desire with concrete sensual detail and stronger escalation.
- **Scorching** — explicit on-page adult intimacy with direct language when requested; no automatic fade-to-black.
- **Inferno** — maximum requested on-page explicitness supported by the configured model while still prioritizing voice, character psychology, pacing, mutual agency, sensory specificity, and aftermath.

Erotic generation is limited to adult participants and keeps the project's adult/consent baseline. Heat controls do not override that floor.

### Tension curve

- **Slow Burn** — small irreversible steps and delayed release.
- **Steady Rise** — each beat increases pressure or intimacy.
- **Pressure Cooker** — restraint, reversals, near-releases, then a break.
- **Flashpoint** — existing charge ignites quickly; the scene spends more time on consequence and emotional change.

The writer can separately tune sensory intensity, dialogue presence, and POV interiority. This avoids treating every high-heat scene as the same rhythm.

### Project craft rules

`style/craft-profile.json` stores project defaults and author-defined prose direction/avoidances. Examples of useful constraints include close POV, restrained metaphor, sharper verbs, more banter, less explanatory narration, avoiding repetitive body-language clichés, or keeping lore imagery tied to a particular magic system.

## Voice Lab and Voice Lock

Voice Lab analyzes a selected passage or current chapter and writes `style/voice-profile.json`. It extracts reusable technique rather than plot:

```text
sentence rhythm
diction / register
imagery and metaphor habits
dialogue behavior
interiority
POV distance
sensual / romantic voice
signature traits
avoidances
```

**Voice Lock** injects that compact profile into future writing. The original prose sample does not need to be sent with every request.

The purpose is not sentence copying. It is to keep a book recognizably itself across ordinary dialogue, action, romance, and explicit scenes.

## Craft Pass

Craft Pass is an optional second inference pass after Write, Continue, or Rewrite. The first pass creates the scene; the second behaves as a line editor.

It preserves events, POV, tense, character identity, relationship meaning, adult consent state, and requested intensity while editing for:

- accidental repetitive cadence;
- generic AI phrasing and filler;
- over-explanation and repeated emotional labels;
- precise verbs and concrete sensory detail;
- character-specific dialogue;
- spatial clarity;
- coherent metaphor/lore imagery;
- purple euphemism when it conflicts with the book voice;
- clinical detachment when it conflicts with the book voice;
- intensity that has become mechanical rather than emotional or dramatic.

Craft Pass intentionally costs another model call, so it is optional and visible in the UI.

## Model and context flow

The frontend stores the configured model connection settings and current craft controls in browser local storage. The backend does not persist an API key supplied for an OpenAI-compatible endpoint.

```text
Author instruction
       +
Active manuscript / selection
       +
Project settings + author profile
       +
Voice Lock + craft profile
       +
Heat level + tension curve
       +
Recent analyzed chapter summaries
       +
Ranked structured narrative memory
       +
Detected participant dossiers
       +
Character knowledge/state + relationship history
       +
Relevant world/story files
       |
       v
Context Compiler / Scene Architect
       |
       v
Model Gateway
       |
       +--> Ollama
       +--> OpenAI-compatible endpoint
       |
       +--> optional Craft Pass
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

Next: editable/correctable canon, relationship history grouping, timeline views, setup/payoff tracking, character-specific voice overrides, scene aftermath/state review, streaming generation, graphical import/recovery, snapshot/history UI, semantic retrieval/embeddings, document export, and native desktop packaging.
