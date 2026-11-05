# Local Neural Voice Lab (Kokoro ONNX)

## Author-first guarantee

EmberWriter remains a writing and publishing application. A neural voice rehearsal is **optional**, is started only by the author, stays on the local machine, and cannot silently replace the manuscript, a proof-approved chapter, or any retail export. Manuscript ownership, casting decisions, and publication approval remain with the author.

## What works

- Assign a built-in Kokoro voice and speaking speed to the narrator or any named character; the mapping is saved with the project and can be reused in later chapters.
- Select a source-anchored passage of up to 1,200 characters in the spoken-text preview, with manually cast dialogue inside it.
- Render a real local, multi-voice 24 kHz PCM WAV rehearsal. Scene segments are narrated in manuscript order and separated with 100 ms of silence.
- Keep source fingerprints and an exact voice/scene plan fingerprint beside each rehearsal. The generated WAV is marked `unapproved_rehearsal`.
- Keep the existing Fish Speech/Drama 3 proof-take adapter separate. The two engines do not pretend to have interchangeable voices or identical expressiveness.

## Hardware and quality limitations

Kokoro ONNX can run on CPU, including on a machine with an 8 GB GPU. This implementation uses ONNX Runtime's default CPU execution path and does not claim GPU acceleration. The voice presets are fixed models, **not cloned character performances**, expressive direction models, or a complete dramatic-acting system.

A successful local WAV does not certify pronunciation, vocal acting, commercial-use rights, mastering, distribution, accessibility or audiobook quality. Author proof listening remains required. These rehearsal takes do **not** feed the finished audiobook queue yet.

## Optional setup / local assets

The optional Python extras are `backend[ kokoro ]` (written as `backend[kokoro]` in installation commands). The model assets are not checked into Git and are not downloaded when the author opens a project.

On Windows, the voice engine expects these two files in:

`%LOCALAPPDATA%\EmberWriter\models\kokoro\`

- `kokoro-v1.0.onnx`
- `voices-v1.0.bin`

Source: `https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1`.

Use the model and voice bundle from the same release. Authors must review model and bundled-voice licenses before commercial distribution. The `kokoro-onnx` runtime is MIT and the upstream Kokoro model is Apache 2.0, but third-party phonemization components can have separate licensing obligations.

Only authenticated local project endpoints are implemented here; a remotely hosted speech endpoint or automatic external manuscript upload is **not** supported.

## Reproducible smoke checks

The optional `backend/smoke_kokoro.py` checks three voices with a synthetic passage. The `backend/smoke_kokoro_scene.py` smoke check exercises the real project API: save voices, tag speakers, prepare an exact scene plan, render audio, and retrieve the WAV. Both use synthetic text only and save output under `%LOCALAPPDATA%\EmberWriter\demos\`. Neither is a substitute for human listening tests.

## Next needed before a complete audiobook

- Controlled, resumable **neural** whole-book jobs with source-fingerprint lock, author approval, change detection, crash recovery, and chapter-scale generation.
- Neural take review, pronunciation editing, retakes by line, and a dedicated performance-quality evaluation interface.
- Source-to-audio alignment and automated missing/duplicated-sentence detection.
- Studio-grade mastering and a separate finished-audiobook export, with license verification and retailer-specific validation.
- Better speaker attribution proposals with unassigned/ambiguous dialogue surfaced for author review.

## Author-led neural book batch (new)

The Audiobook Workshop now contains a **Neural Audiobook Production** panel, distinct from the existing Windows SAPI queue. Authors may create a production batch from the selected Binder Draft, then generate its remaining voice segments while the browser remains open. All work uses the local Kokoro ONNX model, saved narrator/character voices and speeds, and the author's pronunciation dictionary.

Generation is bounded to a maximum of 120 manuscript chapters and 12,000 short segments. Each segment is individually recorded as a PCM WAV with a content fingerprint; complete chapters are assembled into separate draft WAVs. Chapter outputs are always labeled `rendered_unapproved`. The author can listen to and save each draft. No audio is automatically mastered, proof-approved, released, or copied into the existing commercial publishing pipeline.

The queue file is stored in the project at `.ember/kokoro-book/job.json`. **One audio segment is committed at a time.** The browser sends the next request only after the last one finishes, and its Pause button stops after the current segment. Closing the browser or restarting the server leaves the completed chunks on disk. Reopening the project and selecting Generate remaining resumes at the next incomplete segment rather than repeating the whole book.

Manuscript edits, voice/pacing changes, pronunciation changes, or dialogue cast changes invalidate the queued batch. The production desk flags the job as stale and will not offer a stale chapter for normal playback. The author must explicitly create a fresh batch after reviewing changes; old audio files are kept for forensic recovery, not silently reused.

These are *draft audio recordings* without commercial mastering, ASR-based completeness verification, or chapter-level proof-listening approvals. The existing SAPI proof-approval path is deliberately separate until neural output has its own complete review and approval system.

The test script `backend/smoke_kokoro_book.py` runs a **real two-chapter synthetic book** through the FastAPI endpoints, performs local neural inference with a narrator and actor, checks that every segment finishes, then exports assembled chapter WAVs into `%LOCALAPPDATA%\\EmberWriter\\demos`. It does not access user manuscripts or upload anything.
