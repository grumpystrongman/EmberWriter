# EmberWriter 0.15.0 RC2 — Audio Director Preview

**Release status:** public preview / release candidate. Audition recordings are explicitly **unapproved**; not a commercial audiobook certification.

## Highlights
- **Audiobook-only performance manuscript:** immutable source-linked cue sheets saved per chapter; original book text stays unchanged.
- **Correct character voice attribution:** quoted dialogue is split from narration and assigned to explicit speakers. Uncertain speakers block neural rendering rather than silently falling back to the narrator.
- **Audio Director editing:** inspect each line in the Audiobook Workshop, choose a speaking character, and edit emotion and delivery annotations without changing the novel.
- **Fish-compatible direction:** local Fish rehearsal takes can use saved character references and expressive performance direction. Actual expressive rendering requires separately installed/configured Fish Speech; it is not included and was not validated in this RC.
- **Kokoro consistency:** each line renders in its configured voice; previously verified CMU/IPA pronunciation overrides and 1.35-second chapter-heading silences are retained. Kokoro does not inherently honor expressive Fish acting tags.
- **Incremental audio cache:** reuse SHA-verified unchanged synthesis chunks after edits; regenerate only changed speaker, text, voice, speed, IPA, or silence settings.
- **Author review first:** cue sheets, rehearsal audio and M4B are never implicitly approved or published.

## Demonstration and testing
Three chapters of the synthetic original *The Bell Below Low Water* were rendered with five actors (Narrator, Mara, Ivo, Nessa, Sal). All 70 dialogue passages have explicit metadata assignments (30 editor-suggested assignments requiring author approval). Three WAVs and a 17:04 chapter-marked M4B were generated. Exact silence after each chapter title and IPA-rule inclusion were verified. Full backend regression: **559 passed**; after adding cache-reuse tests, the focused tests: **20 passed**; frontend production build passed.

## Limitations and next steps
- Fish voice-server performance, model choice, licensing, and expressivity need a live human listening test.
- Emotion suggestions are intentionally conservative; deep LLM narrative acting direction is not yet delivered.
- Screenshots and audio excerpts are from the synthetic demo, never private project content.
- Clean-install/upgrade and end-to-end UI acceptance remain release gates before GA.
- All generated audition audio requires full author listening and approval.
