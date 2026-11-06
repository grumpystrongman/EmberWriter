# Expressive Audiobook Director — CPU-first implementation and boundaries

**Status:** Feature branch `feature/expressive-cpu-audiobooks`. Author-review-required audio; not a certified full-length public-beta audiobook.

## Why three engines?

Fish Speech S2-Pro and Drama 3 support strong natural-language emotional delivery tags, but Drama 3's official local requirements include a very large NVIDIA GPU. **Do not tell authors that Fish Drama 3 runs on normal CPU laptops.** The app keeps Fish local proof takes as an optional high-hardware comparison, not its only audiobook strategy.

EmberWriter has two GPU-free options:

| Engine | Local model | Emotion control | Whole-book production | Notes |
|---|---|---|---|---|
| Kokoro ONNX + expressive prosody | Existing 82M/ONNX | Author-selected tempo, gentle pitch (FFmpeg Rubber Band), dynamic gain and pauses; **not native acting** | Yes | Default; requires no added model. Pitch requires optional local FFmpeg with Rubber Band; no low-quality resampling fallback. |
| KittenTTS 2 | Separately installed 1.7B 1-bit model, `emb4` weights ~492 MB | **Native** emotion tags + expressive/stable decoder selection; ten native moods, other labels mapped conservatively | Yes, through existing restart-safe source-hash and author proof queue | CPU capable, but Python backend can be slow; optimized C++ backend is not yet integrated. Voice casting is per narrator/character. |
| Fish Speech local | Separate GPU server and author-managed voice references | Model-directed free-form emotion tags and energy descriptors | **Proof takes only** in this integration | Author compares line takes, not automatically incorporated into the finished Kokoro/Kitten audiobook. |

## Author workflow

1. In **Publish → Audiobook → Audio Director**, select a manuscript chapter and reveal all voices/narration.
2. Attribute any ambiguous dialogue. Set emotion (neutral, joy, sadness, grief, anger, fear, urgency, tenderness, uncertainty, relief, determination, excitement, etc.) and intensity 1–5. Save the audiobook-only cue, not prose.
3. Use the **CPU Kokoro take** action to audition acoustic expression (requires Kokoro voice profile). Use the optional **native CPU emotion** take with a separately installed Kitten model and saved character voice. Compare against Fish when available. Listening and final author selection are always explicit.
4. Under **Neural Audiobook Production**, select *Kokoro* or *KittenTTS 2*. The engine choice is frozen into that job. A different model/voice/scene/source edit invalidates the current version.
5. Render in restart-safe segments, listen to the complete chapter, correct individual sections, and explicitly approve exact audio bytes tied to the source hash. Only approved chapters may enter full-book WAV/M4B assembly; final licensing/mastering remains required.

## Optional Kitten installation (not automatic)

KittenTTS 2 uses **Stellon Labs Community License** model weights, distinct from the project's Apache-2.0 code license. As described in its model card, free commercial use has revenue/funding thresholds and redistribution/attribution requirements; get separate authorization if necessary. Review current terms yourself **before** installing for production.

- Model: <https://huggingface.co/KittenML/kitten-tts-2>
- Model license: <https://huggingface.co/KittenML/kitten-tts-2/blob/main/LICENSE.md>
- Supported Python API and offline CPU setup: <https://github.com/KittenML/KittenTTS/blob/main/docs/api.md>
- CPU-optimized upstream (not integrated here): <https://github.com/KittenML/kitten-tts-2-cpp>
- Official Fish requirements: <https://speech.fish.audio/inference/>

In the same optional speech-enabled Python environment used to launch EmberWriter, install the separately licensed `kittenml` package and the `numpy`/`soundfile` runtime. **Do not** install PyTorch/Kitten dependencies into a lightweight writer-only setup.

Download the required official `KittenML/kitten-tts-2` `emb4` model weights, config and decoder assets into a private directory following official upstream instructions; do not simply download every large variant unless you want them. Set `EMBERWRITER_KITTEN_MODEL_DIR` to the absolute local model directory (containing `config.json`) **before** launching the local backend. The app refuses to auto-download weights or use an online model ID in its speech adapter. The first **Load available CPU expressive voices** action may take time to load the model locally.

For CPU-only Windows, Python inference may not meet real-time playback throughput. The model card's realtime claim uses an optimized C++ backend. That backend must be independently integrated and benchmarked before EmberWriter makes the same claim.

## Technical invariants

- The original manuscript is never overwritten; the performance sheet has the exact source hash and quote offsets.
- Any source edit or voice/cue edit freezes previous proof/signoffs. Optional Kitten model change is recorded through local file metadata identity.
- The Kokoro prosody mapping has versioned settings, bounded pitch/gain and pause, and per-take WAV hash. Its pitch step refuses to silently degrade when local FFmpeg Rubber Band is missing.
- Kitten emotion tags are a strict whitelist of the ten model-supported tags: `angry, contemplative, excited, joyful, mundane, nervous, sad, stern, surprised, tender`. Other author intent labels are mapped as **approximations**. The author may not expect individual emotions to sound consistent in every voice.
- The Kitten/Fish transcript path never inserts fictitious words or unrequested laughter/crying/sighing. Existing source text and pronunciations are separate from performance cue text.
- No cloud API or automatic voice uploads are used; no model or speech download occurs upon opening an audiobook project.
- Different engine versions remain separate from any previously approved editions.

## Release quality gates still open

1. Independently assess emotion fidelity and voice stability by **blind listening** across at least 10 emotions, 3 voices, 25 repeated phrases, and both CPU/GPU providers where available.
2. Benchmark real full-book GPU-free generation runtime and memory on **actual low-end hardware** (not just this development machine).
3. Verify phoneme/dictionary behavior and line-by-line coverage for Kitten. Kitten currently **rejects unsupported IPA rules** rather than pretending to apply them; direct offline pronunciation override quality needs independent tests.
4. Verify cross-chapter volume matching, character continuity, pauses, no doubled/missing lines, full listen/retake, licensing, M4B tagging and retailer-specific mastering.
5. Run actual input/output audio tests on both engines. Mocked tests prove routing and safety, **not** model quality.

Do not promote the beta ship gate based on a subset of synthetic tests.
