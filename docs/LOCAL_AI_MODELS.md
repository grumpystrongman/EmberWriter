# EmberWriter Local AI Models

EmberWriter uses local Ollama models through intent-specific capability slots instead of treating one model as best for every authoring task.

## Managed capability map

Auto setup installs four managed models:

- **Adult explicit:** `hf.co/mradermacher/Qwen3.5-4B-NSFW-ARA-Heretic-Literotica-i1-GGUF:Q4_K_M`
- **General prose:** `hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M`
- **Character / dialogue:** `hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M`
- **Planning / fast:** `R4C3R/qwen3-8b-heretic:q4_k_m`

These are persisted in `.ember/local-models.json` as `adult_explicit_model`, `general_prose_model`, `character_model`, `planning_model`, and `fast_model`.

The global fallback remains prose-first. A stale ordinary-fiction model selection repairs toward Magnum/Pygmalion/Qwen, not toward the erotica specialist.

## Adult-explicit specialist

The managed Qwen3.5 4B Literotica Q4 model is the dedicated explicit-sex-scene model. EmberWriter does not use it for ordinary fiction, planning, or routine character dialogue.

On September 20, 2026, the exact Q4_K_M model was run under llama.cpp in an isolated GitHub Actions proof. The generated prose was never printed or uploaded. The deterministic verifier reported:

- 1,372 words
- first direct sexual action at word 29
- 34 direct-action sentences
- Avery's penis canon represented directly
- no conflicting vagina/vulva/clitoris anatomy
- manual, oral, and penetrative sexual action present
- both named climaxes supported
- zero refusal/meta output
- zero domestic/scenery drift
- zero consent re-litigation

The generated output SHA-256 was:

`95c9b55b72965adc59da1b026e8d771c5c9a9538385478d98fc0760edd234d51`

The local acceptance contract is version 4 and mirrors this proof more closely: 900–1,600 words, action by word 140, at least 12 direct-action sentences, correct hard body canon, required physical beats, both named climaxes, and no setup/domestic drift.

If the specialist fails local validation, EmberWriter records that failure. It does **not** silently substitute Magnum, Pygmalion, or another general model for explicit sex scenes.

## Intent routing

Studio's **Auto-match my writing** mode maps author intent to capabilities:

- **Adult / high heat:** Qwen3.5 4B Literotica specialist.
- **General fiction:** Magnum-v4-12B.
- **Character & dialogue:** Pygmalion-3-12B.
- **Plotting & analysis:** managed Qwen fast/planning model.
- **Fast profile:** favors low-latency models, except explicit adult scenes still stay on the 4B adult specialist because it is already the smallest managed specialist.
- **Manual selection:** remains available for experimentation, but explicit local adult generation is force-routed to the dedicated specialist when it is installed.

The backend also enforces the adult route before the scene prompt is built, so a stale UI selection cannot accidentally send an explicit scene to a general-purpose model.

## Adult specialist generation contract

The adult model receives a compact scene-first prompt rather than the full general-purpose Studio instruction stack. EmberWriter:

- keeps hard body / embodiment canon at the top of context,
- trims broad lore and unrelated roadmaps,
- treats established consent as settled story state,
- requires direct anatomical and physical description when requested,
- requires the central encounter to occupy the response,
- preserves character voice without letting symbolism or emotional analysis displace the physical scene,
- and skips the generic Craft Pass afterward so a second model cannot soften or derail a successful explicit draft.

## Character body canon

EmberWriter never infers intimate anatomy from gender identity. For characters whose anatomy matters on page, record author-confirmed facts under:

`## Embodiment & intimate canon`

That block is promoted into high-priority generation context and checked deterministically before an adult scene can pass verification.

## Commercial-product note

The upstream Magnum-v4-12B and Pygmalion-3-12B releases are Apache-2.0 candidates and are used as the cleaner general/character foundation for future commercial packaging.

The explicit Literotica fine-tune is currently treated as **runtime-download only** and marked `adult_specialist_commercial_license_review_required=true`. EmberWriter should not bundle, redistribute, or host those exact weights commercially until the fine-tune and quantized redistribution license chain has been reviewed. The product architecture intentionally keeps the adult capability slot replaceable so a commercially clean in-house adapter can later occupy the same slot without changing scene-generation logic.

## Install

From PowerShell:

```powershell
.\install.ps1
```

Auto setup installs the four managed capability models.

To install only the proven 4B adult specialist:

```powershell
.\install.ps1 -AdultModelTier 4b
```

To skip local model download when using another provider:

```powershell
.\install.ps1 -SkipModelDownload
```

Long context windows, GPU offload, the OS, and EmberWriter itself consume RAM/VRAM in addition to model weights.
