# EmberWriter Local AI Models

EmberWriter is designed to work with local Ollama models and OpenAI-compatible local servers. Model choice is capability-based: adult/high-heat drafting, general prose, character/dialogue work, and planning can use different installed models.

## Managed writing candidates

Auto setup now provisions three candidates that participate in intent routing and adult-scene acceptance:

- **Adult / roleplay candidate:** `hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M`
- **Creative prose candidate:** `hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M`
- **Fast / adult candidate:** `R4C3R/qwen3-8b-heretic:q4_k_m`

Pygmalion-3 is a roleplay-focused Mistral-Nemo fine-tune. Magnum-v4 is a prose/character candidate. The fast Qwen variant participates in the same adult-scene bakeoff because parameter count is not a quality guarantee for a specific authoring task. EmberWriter trusts measured scene delivery over the model label.

Both selected 12B upstream model releases are Apache-2.0 licensed. That makes them substantially cleaner candidates for a future commercial EmberWriter than models whose base or merge licensing is research-only, non-commercial, or ambiguous. Quantized redistributions should still be reviewed before shipping a bundled binary or hosted service.

## Real-model adult bakeoff

Installation and startup run EmberWriter's real local-model acceptance contract against every installed managed adult candidate. The bakeoff does not award a model merely because its name contains words such as "uncensored" or "roleplay."

The winner must pass the adult-scene delivery gate on the author's machine. Results are written to:

`.ember/model-bakeoff.json`

When a candidate passes, the winning model is also persisted as `accepted_adult_model` / `adult_model` in:

`.ember/local-models.json`

You can rerun the bakeoff manually:

```powershell
backend\.venv\Scripts\python.exe -m app.model_bakeoff --attempts 3
```

The current version-3 acceptance test measures direct scene delivery, action onset, sustained concrete action, a 500–1,000 word core-only window, participant fidelity, completion, drift, and hard body-canon compliance. Its synthetic Muna fixture explicitly establishes a penis and explicitly excludes vagina/vulva/clitoris anatomy, so a candidate that invents conflicting anatomy cannot win. It is intentionally a product acceptance test rather than a generic language-model benchmark.

## Intent-based routing

Studio's **Auto-match my writing** mode routes by author intent:

- **Adult / high heat:** prioritize the locally accepted bakeoff winner, which may be the 8B fast model or a larger creative/RP model.
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

The Q4 12B candidates are roughly in the 7–8 GB weight range each before context/KV-cache and application overhead; the 8B candidate is smaller. Installing all managed candidates therefore uses materially more disk than the previous single-model default. Long context windows, the operating system, EmberWriter, and GPU offload also consume RAM/VRAM.

For best long-form results, use Voice Lock / Voice Fingerprint, Story Memory, Character Chemistry, Scene Architect, delivery-scope enforcement, and the real-model acceptance gate together rather than relying on the base model alone.


## Character body canon

EmberWriter never assumes intimate anatomy from gender identity. For characters whose anatomy matters on page, record the author's confirmed facts under the Character Studio dossier section:

`## Embodiment & intimate canon`

State relevant present and absent anatomy explicitly when needed. That block is promoted ahead of ordinary dossier prose during scene generation and is checked deterministically before a local Studio scene can pass verification.
