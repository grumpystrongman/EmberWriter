# Managed image engine

On Windows, EmberWriter installs and manages a local Stable Diffusion WebUI-compatible image engine as part of normal setup.

## Default

`install.ps1` installs **Stable Diffusion WebUI Forge** under `.ember/image-engine/forge`, using Forge's upstream GitHub repository. EmberWriter installs Git and Python 3.10 through `winget` when they are not already available, because the WebUI runtime has different Python requirements from EmberWriter's Python 3.11 backend.

Unless `-SkipImageModelDownload` is supplied, setup also downloads the public Stable Diffusion 1.5 `v1-5-pruned-emaonly.safetensors` checkpoint from Hugging Face and verifies its published SHA-256 before accepting it. The model remains subject to its CreativeML Open RAIL-M license.

The managed runtime is deliberately stored beneath the repository-local `.ember/` directory, which is ignored by Git. Models, virtual environments, logs, and generated runtime files are never application source files.

## Launch behavior

`start.ps1` starts the managed image engine automatically with:

- `--api`
- `--port 7860`
- `--no-download-sd-model`

The WebUI therefore exposes the `/sdapi/v1` API already used by EmberWriter. If another compatible server is already running at the configured address, EmberWriter reuses it rather than launching a second copy.

When EmberWriter starts the managed engine itself, it records the process ID and stops that process tree when the EmberWriter development launcher exits. Standard output and error logs are written beneath `.ember/logs/`.

Image-engine startup or installation failure is non-fatal: EmberWriter still opens, and the in-app image-server status control provides connectivity diagnostics.

## Installer options

Use Forge (default):

```powershell
./install.ps1
```

Use classic AUTOMATIC1111 instead:

```powershell
./install.ps1 -ImageEngine automatic1111
```

Install the WebUI but do not download the baseline checkpoint:

```powershell
./install.ps1 -SkipImageModelDownload
```

Skip the managed image engine entirely:

```powershell
./install.ps1 -SkipImageEngineInstall
```

Start EmberWriter without installing or launching a managed image engine for that run:

```powershell
./start.ps1 -SkipManagedImageEngine
```

Rerunning `install.ps1` updates the managed WebUI checkout with a fast-forward pull. For a clean runtime reinstall, the underlying installer also supports:

```powershell
./scripts/install-image-engine.ps1 -Engine forge -ForceReinstall
```

## Storage and model size

The baseline Stable Diffusion 1.5 checkpoint is approximately 4.27 GB. Forge creates its own virtual environment and may download GPU/runtime dependencies on first launch, so the complete image runtime requires additional disk space beyond the checkpoint itself.
