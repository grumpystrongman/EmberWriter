# EmberWriter Local AI Models

EmberWriter is designed to work with local Ollama models and OpenAI-compatible local servers. Model choice is capability-based: adult/high-heat drafting, general prose, character/dialogue work, and planning can use different installed models.

## Managed 12B candidates

Auto setup now provisions two 12B creative-writing candidates plus the Fast 8B fallback:

- **Adult / roleplay candidate:** `hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M`
- **Creative prose candidate:** `hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M`
- **Fast fallback:** `R4C3R/qwen3-8b-heretic:q4_k_m`

Pygmalion-3 is a roleplay-focused Mistral-Nemo fine-tune and is the first candidate for explicit adult scene delivery. Magnum-v4 is kept as a separate prose/character candidate rather than assuming one model should be best at every writing task.

Both selected 12B upstream model releases are Apache-2.0 licensed. That makes them substantially cleaner candidates for a future commercial EmberWriter than models whose base or merge licensing is research-only, non-commercial, or ambiguous. Quantized redistributions should still be reviewed before shipping a bundled binary or hosted service.

## Real-model adult bakeoff

Installation runs EmberWriter's existing real local-model acceptance contract against both 12B candidates. The bakeoff does not award a model merely because its name contains words such as "uncensored" or "roleplay."

The winner must pass the adult-scene delivery gate on the author's machine. Results are written to:

`.ember/model-bakeoff.json`

When a candidate passes, the winning model is also persisted as `accepted_adult_model` / `adult_model` in:

`.ember/local-models.json`

You can rerun the bakeoff manually:

```powershell
backend\.venv\Scripts\python.exe -m app.model_bakeoff --attempts 3
```

The current acceptance test measures direct scene delivery, length compliance, participant fidelity, completion, drift, and the deterministic explicit-delivery gate. It is intentionally a product acceptance test rather than a generic language-model benchmark.

## Intent-based routing

Studio's **Auto-match my writing** mode routes by author intent:

- **Adult / high heat:** prioritize Pygmalion-3, then other accepted adult-capable creative models.
- **Character & dialogue:** prioritize Magnum-v4 and other roleplay/prose specialists.
- **General fiction:** prioritize broad prose-capable models.
- **Plotting & analysis:** prioritize instruction-following/reasoning models.
- **Manual model selection:** disables automatic switching until the author turns it back on.

This separation is deliberate. A commercial EmberWriter should maintain a model capability registry rather than assuming a single model is optimal for every authoring task.

## Install

From PowerShell in the EmberWriter repository:

```powershell
.\install.ps1
```

Force the smaller model:

```powershell
.\install.ps1 -AdultModelTier 8b
```

Force the 24B experimental high-heat model:

```powershell
.\install.ps1 -AdultModelTier 24b
```

Skip model download when using LM Studio, vLLM, or another provider:

```powershell
.\install.ps1 -SkipModelDownload
```

## Commercial-product note

Do not equate "locally downloadable" with "commercially shippable." Before bundling, redistributing, or operating any third-party model as a hosted EmberWriter service, verify the license of the exact upstream weights, base model, fine-tune, and quantized redistribution being shipped. Keep model identifiers and license metadata in the product catalog so a model can be disabled or replaced without changing scene-generation logic.

## Hardware notes

Each Q4 12B candidate is roughly in the 7-8 GB weight range before context/KV-cache and application overhead. Installing both therefore uses materially more disk than the previous single-model default. Long context windows, the operating system, EmberWriter, and GPU offload also consume RAM/VRAM.

For best long-form results, use Voice Lock / Voice Fingerprint, Story Memory, Character Chemistry, Scene Architect, delivery-scope enforcement, and the real-model acceptance gate together rather than relying on the base model alone.
