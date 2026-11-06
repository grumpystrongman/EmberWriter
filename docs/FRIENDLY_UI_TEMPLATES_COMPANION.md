# Author-first writing workspace, format templates and Ember companion

**Scope:** `feature/friendly-writing-companion-templates` (stacked on expressive-audiobooks work, which itself is stacked on the author-first reference PR). An author-controlled usability slice, not a finished publishing product.

## First-run author experience

1. Open EmberWriter and choose **＋ New writing** in the writing toolbar. A new user can start without creating a project beforehand.
2. Search by genre or form. The catalog currently includes **Horror novel, Science fiction novel, Fantasy novel, Mystery / thriller, Romance novel, Literary fiction, Short story, Flash fiction, Personal essay, Academic essay, Film/TV screenplay, Stage play, Podcast/audio drama script and Poetry** (14 choices).
3. Inspect **Starting page** and **Writing guidance** before committing. Enter a new project name if needed, and a document title. **Create my writing page** is the only action that writes. It creates a separate manuscript file and an editable `style/templates/...` guide. If a name exists, the new document gets a unique path; no existing work is overwritten.
4. Opened documents use format-aware editor typography: typewriter-style for screenplay/stage/audio scripts, book-serif for essays/short fiction, narrower poetic page for verse. The context bar says which format is active.
5. When generating AI prose with an active template document, the app adds the **specific author-editable style guide for that file** to the existing author-profile/story context. The global author's voice stays authoritative. A style guide is not story canon.

**Important limits:** The screenplay is an approachable Markdown/plain-text screenplay draft, **not** a guaranteed Fountain/FDX-compliant professional export or correctly paginated shooting script. Stage formatting similarly is a drafting scaffold, not a final typeset production script. Citation placeholders are explicit; no sources are fabricated by the essay template.

## Ember the writing sidekick

The small floating Ember character is optional and dismissible. It offers relevant opening suggestions for Write, Plan and Publish and an integrated **Start something new** action. Reduced-motion preferences disable its idle motion.

Ember can answer:
- **How to use the app:** route to existing Write, Plan, Analyze, World, Studio and Publish tools; help with templates, references, editorial review and audiobook.
- **What is in this project:** project title and file-name metadata without reading manuscript contents. For actual character/plot questions, **Let Ember read matching passages from this book (this question only)** must be checked per question.
- **Where an answer came from:** opt-in project retrieval returns bounded, source-labeled snippets from manuscript, characters, scenes and world documents, alongside existing extracted story memory (which is labeled as potentially unverified). Source cards can navigate to original files.
- **With or without a model:** offline mode shows useful app help and matching source excerpts. Choosing an installed **local Ollama** model enables contextual natural-language answers with numbered sources. No cloud fallback, no automatic canon changes, no permission to execute edits or publish.

Book-context retrieval is intentionally bounded (~4.3K characters across no more than 7 snippets). External model output is treated as suggestions, never verified truth. The model is told to treat story excerpts as untrusted data, not directives. Project file names/metadata can be supplied without the checkbox; actual prose requires it.

## Verification

- TypeScript/Vite production build: **PASS**.
- New focused Python tests: genre catalog/preview/create, non-overwrite, guide-to-generation context, project search privacy and no unauthorized manuscript changes: **PASS**.
- Focused Python lint: **PASS**.
- Real headless Edge UI walkthrough on a synthetic temporary project: **PASS**. From an empty app, clicked New writing, selected Film/TV screenplay, named a new project, created the document, verified the screenplay editor mode, opened Ember, asked how to write a screenplay, opted into project retrieval for one question, observed linked source snippets, then reduced viewport to **390 px**. No browser page errors and no document-wide horizontal overflow were found.
- A complete human UX evaluation, accessibility audit with assistive technology, screen-reader focus testing, broader display/browser verification and author research remain outstanding.

This feature is not intended to rewrite chapters without review. "AI help" answers are read-only. New template creation requires the author's explicit click.

## Next iteration recommendations

- Guided contextual lessons that spotlight the real control on the screen rather than just naming workspaces.
- User-chosen persistent project conversation memories/decisions, with edit and deletion controls and strict provenance.
- True document-mode schema for screenplay (scene/character/dialogue elements) and final industry-standard Fountain/FDX/PDF export; stage script typesetting.
- Dedicated nonfiction citation manager and fact-checking workflow.
- Proper end-to-end automated accessibility and screenshot regression suite.
