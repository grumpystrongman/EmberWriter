# EmberWriter — author-first finishing experience

Status: product direction and acceptance criteria, not a claim of implementation. Preserve existing production gates in BETA_SHIP_GATES.md.

## Product principle

The author is the director. AI can propose, write, critique, narrate and organize, but cannot silently establish canon, replace approved prose, accept a chapter, finalize a voice performance, or publish. The primary interface is writing, not managing models or configuration.

## 1. One idea → one complete novel, with conversation

- Start from one unstructured prompt (including genre, story idea, length, voice, limits and references).
- Ask the smallest useful set of *prioritized*, conversational questions; never require filling dozens of fields upfront. Offer defaults, "decide later", and "surprise me".
- Summarize decisions as an editable creative brief: premise, characters, style, content boundaries, major beats and target length. Label model-suggested assumptions separately from author-confirmed facts.
- Show an author-owned journey: **Idea → Shape → Outline → Draft → Revise → Finish**. Allow jumping backward without losing author work.
- Author reviews the high-level blueprint and can approve once, then run drafting with configurable approval checkpoints: chapter-by-chapter (default), act-by-act, or draft-all-as-candidates. Even the most autonomous mode requires explicit approval before material enters the canonical manuscript.
- During drafting, let the author interrupt in plain English: "Make her less trusting", "move the reveal", "keep chapter seven". Surface what will change, affected chapters and existing approvals before reworking any material.
- Persist checkpointed jobs, sources, decisions, story memory, rejected alternatives and exact revision diffs. Resume after restart without duplicate chapters or overwritten manuscript text.
- Finish only when the complete planned Binder is coherent, author-approved, edited and exportable. Never claim literary quality based solely on automatic lint/AI scores.
- Acceptance journey: a brand-new author can provide a single sentence, answer clarification in a chat, review and approve the plan, produce a 60k+ word 20+ chapter *candidate* novel with restart recovery, approve/revise it, and export the same edition. Full author reading remains essential.

## 2. Audiobook: expressive and modest-hardware first

Existing assets: local SAPI, experimental Kokoro ONNX, Fish proof-takes, sound checks and M4B assembly. Those are not evidence of finished neural audiobook production.

- Offer **Lightweight (CPU-first)**, **Balanced**, and **Expressive (optional stronger hardware)** choices with truthful installation size, RAM/VRAM expectations and offline/licensing disclosures. Never require Fish Speech or a large GPU for the default audiobook path.
- Build on CPU-friendly ONNX/Kokoro-style synthesis first; benchmark real-time factor, quality and memory on actual low-resource Windows machines. Fish Speech is an optional quality/reference comparison, not a promised small-model drop-in equivalent.
- Authors assign narrator and character voices; attach precise scene/line anchors and editable delivery labels: neutral, joy, grief, anger, fear, whisper, excitement, exhaustion, urgency, sarcasm, etc. Support energy, pace, pause, pronunciation, dialogue attribution and intensity where the chosen engine actually supports them. Do not claim a slider controls an unsupported emotion.
- Separate *expressive directions* from actual acoustic capability. Where engine cannot do a requested delivery, show the limitation and allow alternate takes/providers or a human narration workflow.
- Queue chunked, resumable chapter rendering on CPU. Persist per-line source hash, voice/model version, direction, output file hash and playback timestamps. Changes invalidate only relevant takes.
- Use source-to-audio text coverage checks and author-facing proof notes, retakes, A/B comparisons and chapter signoff. Show character attribution uncertainty for manual resolution.
- Create M4B/approved chapter delivery only from one verified manuscript edition and all author-approved takes, with retailer-specific specifications and licensing signoff.
- Acceptance journey: a full novel can be rendered on specified no-discrete-GPU hardware, re-rendered after edits, completely proof-listened, and exported without missing, doubled or stale lines.

## 3. Gentle, understandable UI

- Home: **Continue writing**, **Start a story**, **Review drafts**, **Make an audiobook**. Show a single recommended next action, a human-readable progress summary and "why this matters".
- Write is the central workspace. Advanced editorial, worldbuilding, model settings, diagnostics and generation controls should be progressive disclosure, not a wall of forms.
- Use ordinary words first: "Draft chapter" instead of "inference job"; "Your approved story" instead of "canonical state"; "Hear this scene" instead of "synthesize".
- Never show a generic spinner for long-running work. Show current chapter/scene, what is saved, pause/resume and what needs the author's decision. Keep originals and undo.
- Provide comfortable typography, a distraction-free writing mode, good keyboard and screen-reader paths, large targets, reduced motion and readable errors with direct remedies.
- Measure the onboarding against first-time fiction writers, not just existing power users.

## 4. Ember, the contextual writing companion

- A small optional assistant inspired by Clippy's *helpfulness*, not intrusive animation or unsolicited interruptions. Name and character are provisional; accessibility must not depend on a mascot.
- Questions work in plain language: "What should I do next?", "Why is this draft blocked?", "Can you help my dialogue?", "Where are my characters?", "How do I narrate this chapter?"
- Context includes the current workspace, selected chapter, project status, author-confirmed canon and available tool actions; never assume access to unrelated personal documents.
- Responses distinguish **Explain**, **Suggest**, **Preview change**, and **Do approved action**. High-impact edits, approvals, deletion, publication and external transfers always require explicit confirmation. Show sources for narrative claims.
- Conversation stays project-local by default and never transmits manuscript/images outside the selected provider without informed opt-in. A writer-only/no-model installation must still offer an offline help guide.
- Make the helper dismissible, movable and keyboard accessible. It must not cover the manuscript or auto-write in response to general help requests.

## 5. Visual inspiration in author context

- Authors can paste clipboard images copied from websites or captured screenshots, drag/drop an image, or select a local file. Images can be associated with a character, place, scene, chapter or moodboard.
- Save originals as separate project-local **Reference** assets, not silently replacing existing art. Support an author note: "Borrow the lighting, not the costume"; show thumbnail and attribution/source URL field for later rights review.
- A text-only model must not pretend to have seen an image. To use the visual as AI input, explicitly select a compatible vision model/provider or provide an author-written description; show what was passed to the model.
- A reference is inspiration, not confirmed canon. The author must approve specific derived visual/story details before they influence established character descriptions or future writing.
- Adding a new image must never silently mutate approved story text; references cannot be republished as licensed cover art without rights review.
- First slice implemented on the branch: paste/drop images into Visual Studio's existing local upload and reference library. Context-aware cross-workspace paste, source URL capture, vision-model interpretation and rich annotations remain future work.

## Delivery order

1. Validate image paste/drop, upload errors, non-overwrite behavior and accessibility.
2. Build companion with deterministic help/route suggestions, then optional LLM contextual answers and action previews.
3. Implement conversational project brief and author approval workflow on top of the existing Book Studio/Production Conductor.
4. Add per-line expressive direction, CPU-first rendering benchmarks, audiobook proof/signoff and edition verification.
5. Conduct complete novel, full audiobook, fresh Windows installation and human usability acceptance tests before promoting public beta.

**Release constraint:** no user-facing claim that any of these experiences is complete unless exercised on the exact commit and release artifact.
