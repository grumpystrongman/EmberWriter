# EmberWriter — 10-minute author-first demo review package

**Status:** rendered, validated, and uploaded to a **draft, unpublished GitHub release** for private product review.

- [Open the draft review release](https://github.com/grumpystrongman/EmberWriter/releases/tag/untagged-bb8b7529172da54fa2ba) (authorized repository collaborators only until publication)
- Local Windows file: `%USERPROFILE%\Videos\EmberWriter\EmberWriter-Author-First-10-Minute-Demo.mp4`
- Final runtime: **600.000 seconds**, 1920 × 1080, 24 fps, H.264 video and AAC stereo audio, ~24.6 MB.
- MP4 SHA-256: `49f01a55b54380b4a9e82128b5926c80a2f5120b369b1fEC1196FC75616F868D`. Compare case-insensitively.
- Included assets: MP4, English SRT captions, chapter timecodes (JSON), full narration transcript (TXT), thumbnail (JPEG).
- Narration: local neural Kokoro ONNX voices `af_heart`, `af_nova`, `am_michael`. Music: original synthesized instrumental underscore, not licensed commercial music.
- Visuals: real running-app captures from an **isolated synthetic-only preview**, designed into narrated chapter cards with explanatory callouts. This is a *narrated screenshot-based feature tour*, not a live cursor-click screencast; precise button-by-button interaction demonstrations would be a distinct additional deliverable.

## Editorial running order

| Start | Segment |
|---|---|
| 00:00 | The author comes first |
| 00:37 | Writing workspace and chapter library |
| 01:08 | Genre and format templates |
| 01:44 | Guided AI planning and chapter drafting |
| 02:23 | Characters and worldbuilding |
| 02:57 | Series Vault |
| 03:35 | Canon Graph and author approval |
| 04:11 | Time-aware series knowledge |
| 04:47 | Continuity Guardian |
| 05:22 | Consequence Map |
| 06:00 | Professional Ember series librarian |
| 06:33 | Visual references |
| 07:09 | Neural audiobook rehearsals and direction |
| 07:55 | Recovery Center and independent backups |
| 08:35 | Editorial and publishing workflows |
| 09:12 | The author-first promise and closing |

## Marketing and legal accuracy

Present the video as a product preview, not as evidence that every workflow is commercially production-ready. This branch is under draft code review ([PR #126](https://github.com/grumpystrongman/EmberWriter/pull/126)); source-backed canon tools are still being integrated. Do not imply rights to the works of any famous author, perfect prevention of data loss, unconditional GPU-free performance of every model, or automatic compliance with publishing attribution rules. The sample universe and text are synthetic.

Backups and recovery are part of the product demonstration, but local-only copies do **not** protect against physical disk failure. A second independent encrypted storage location and verified recovery drill are strongly recommended.

## Validation evidence

- Real UI captured in desktop Edge from the running React/FastAPI app, including a live synthetic continuity conflict, consequence analysis, Ember source-cited answer, and backup verification.
- Mobile regression at 390 px: no horizontal scrolling, Library panel collapsed, non-overlapping Import and Ember launch controls.
- Frontend TypeScript/Vite build succeeded; 609 backend tests passed, 1 skipped; full Ruff lint passed.
- Final video verified with ffprobe as exactly 600 seconds, 1080p, 24 fps, AAC stereo, and no detected black-screen stretches.
- A permanent mobile layout guard was added to `frontend/ux-visual-smoke.mjs`.

## Publishing checklist

1. Watch the MP4 end-to-end, especially the neural voice pronunciation and the audiobook section.
2. Confirm visual screenshots and product claims still match the intended public release.
3. Review the captions for proper names, punctuation, and timing; the SRT is aligned from the narration script and should receive a human accessibility pass.
4. Re-record the tour after significant UI changes; don't publish stale screenshots.
5. When approved, publish the GitHub draft release or upload the MP4/captions/thumbnail to the chosen marketing platform.
