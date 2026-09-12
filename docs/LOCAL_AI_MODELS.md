# EmberWriter Local AI Models

EmberWriter is designed to work well with local Ollama models and OpenAI-compatible local servers.

## Recommended adult-fiction model

The Windows installer selects a model based on available system memory:

- **24 GB+ RAM:** `R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m`
- **Below 24 GB RAM:** `R4C3R/qwen3-8b-heretic:q4_k_m`

Both are community creative-writing / roleplay variants intended for local use with reduced refusal behavior. EmberWriter does not add an extra sanitizing layer for consensual adult fiction. The configured model still determines what it is technically capable of producing.

The 14B model is preferred when the machine can support it because longer fiction generally benefits from the extra capacity. The 8B model is the practical fallback and is substantially lighter.

## Install

From PowerShell in the EmberWriter repository:

```powershell
.\install.ps1
```

Force the smaller model:

```powershell
.\install.ps1 -AdultModelTier 8b
```

Force the larger model:

```powershell
.\install.ps1 -AdultModelTier 14b
```

Skip model download when using LM Studio, vLLM, or another provider:

```powershell
.\install.ps1 -SkipModelDownload
```

The installer records the selected model in `.ember/local-models.json`.

## General-fiction option

For users who prefer a mainstream general-purpose model for non-adult drafting, Mistral Small 3.1 is a strong local option when hardware permits:

```powershell
ollama pull mistral-small3.1
```

It is a much larger download than the default 8B writing model, so EmberWriter does not pull it automatically.

## Hardware notes

Quantized model files are only part of the memory requirement. Long context windows, the operating system, EmberWriter, and GPU offload also consume RAM/VRAM. If the 14B model is slow or unstable, rerun the installer with `-AdultModelTier 8b`.

For best long-form results, use Voice Lock / Voice Fingerprint, Story Memory, Character Chemistry, and Scene Architect together rather than relying on the base model alone.
