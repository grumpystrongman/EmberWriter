# Author-first finishing slice — implementation report

Branch: `feature/author-image-paste-references` (draft PR #122). This is a functional feature slice, not certification of a finished novel or audiobook.

## Implemented

1. **Capture images while writing.** A toolbar **Reference** action opens a scoped dialog for clipboard image paste (Ctrl+V), drag/drop, or a file selection. Capture author notes, optional attribution URL, and current-chapter association. Files use existing project-local append-only Visual Canon infrastructure, not manuscript text. Large/unsupported uploads report errors. Advanced Visual Studio also supports clipboard/drop, attribution, and descriptions.
2. **Ask local vision AI about a reference.** Visual Studio provides opt-in picture interpretation via an explicitly selected local Ollama vision-capable model. The backend sends a reduced image to loopback `127.0.0.1:11434` only; no cloud fallback or manuscript upload. AI observations are offered for author review; the model cannot approve canon or modify prose. Text-only models do not qualify.
3. **Ember companion.** A dismissible, keyboard-accessible, read-only helper with useful offline navigation and an optional local Ollama answer path. It knows the current workspace and provides explanations rather than edits. It sends no manuscript text or image bytes to the help model. Focus mode hides the helper.
4. **A one-idea conversational starting point.** Book Studio now asks for an initial idea, then a small set of optional character, stakes, ending and style answers; `Surprise me later` defers a decision. The author reviews the resulting direction in the existing Book Studio blueprint and uses the existing optional local outline generator and human approval workflow. This intake is deliberately guided, not yet a dynamic LLM clarification agent.
5. **Author-selected audiobook energy.** Audio Director now accepts a 1–5 energy hint. CPU-friendly Kokoro ONNX maps it to a deliberately modest speaking-speed adjustment (0.92× to 1.08× relative to the configured rate, clamped to engine bounds). It is not true model-conditioned emotional acting. Fish rehearsal still uses descriptive direction tags and remains optional. Author proof listening and take approval remain required.

## Verification performed

- On an isolated cloned branch (not the user's live manuscript installation), TypeScript + Vite production build passes.
- Focused backend tests passed: 21 tests across visual asset safety, opt-in vision, Ember helper, Audio Director and Kokoro book mechanics.
- Python lint for the new route modules and their tests was run. A test import sorting warning was fixed afterward; rerun it on the latest commit.
- Real browser end-to-end paste/drop testing, small-screen layout/accessibility, actual GPU-free full-book neural rendering and clean Windows install remain to be performed.
- Existing public-beta ship gates remain **HOLD** until a human-accepted 60k+ word novel, complete proof-listened matching audiobook and independent clean-install evidence are demonstrated on the same release artifact.

## Next milestones

1. UI interaction and keyboard-only testing, responsive 390/900/1440px screenshots, and complete system checks.
2. A genuinely dynamic, project-persisted LLM clarification session with decision log and revision-aware chapter blueprint; the first wizard is merely structured author intake.
3. Reference interpretation integrated into scene/character/world brainstorm prompts with explicit author choice of *which* details may influence the AI.
4. A model capability/benchmark selector for CPU-first and optional expressive audio, robust scene-by-scene voice performance, full-book source-to-audio coverage checks, and actual hardware benchmarks.
5. A richer action-planning companion that previews changes and always asks for author authorization before any write.

Avoid marketing the lightweight energy/pacing adapter as equivalent to Fish Speech's expressive synthesis.
