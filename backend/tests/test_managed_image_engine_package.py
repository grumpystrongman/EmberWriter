from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_windows_installer_manages_forge_by_default() -> None:
    install = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")
    image_install = (REPO_ROOT / "scripts" / "install-image-engine.ps1").read_text(
        encoding="utf-8"
    )

    assert '[string]$ImageEngine = "forge"' in install
    assert "lllyasviel/stable-diffusion-webui-forge.git" in image_install
    assert "AUTOMATIC1111/stable-diffusion-webui.git" in image_install
    assert 'launch_args = @("--api", "--port", "$Port", "--no-download-sd-model")' in image_install
    assert "http://127.0.0.1:$Port" in image_install


def test_baseline_checkpoint_is_pinned_and_verified() -> None:
    image_install = (REPO_ROOT / "scripts" / "install-image-engine.ps1").read_text(
        encoding="utf-8"
    )

    assert "v1-5-pruned-emaonly.safetensors" in image_install
    assert "6ce0161689b3853acaa03779ec93eafe75a02f4ced659bee03f50797806fa2fa" in image_install
    assert "Get-FileHash -Algorithm SHA256" in image_install
    assert "CreativeML Open RAIL-M" in image_install


def test_windows_launcher_auto_starts_and_cleans_up_managed_engine() -> None:
    start = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")
    image_start = (REPO_ROOT / "scripts" / "start-image-engine.ps1").read_text(
        encoding="utf-8"
    )

    assert "start-image-engine.ps1" in start
    assert "install-image-engine.ps1" in start
    assert "taskkill.exe /PID $ImageEnginePid /T /F" in start
    assert "/sdapi/v1/options" in image_start
    assert 'Start-Process -FilePath "cmd.exe"' in image_start


def test_launchers_pin_project_storage_to_install_root() -> None:
    windows = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")
    windows_hosted = (REPO_ROOT / "start-hosted.ps1").read_text(encoding="utf-8")
    unix = (REPO_ROOT / "start.sh").read_text(encoding="utf-8")
    unix_hosted = (REPO_ROOT / "start-hosted.sh").read_text(encoding="utf-8")

    assert '$DefaultDataRoot = Join-Path $Root "data"' in windows
    assert "$env:EMBER_DATA_DIR = $DefaultDataRoot" in windows
    assert "Recovered existing EmberWriter projects from legacy data location" in windows
    assert "-WorkingDirectory $Root" in windows
    assert "-PassThru" in windows
    assert '$env:EMBER_DATA_DIR = Join-Path $Root "data"' in windows_hosted
    assert 'export EMBER_DATA_DIR="${EMBER_DATA_DIR:-$ROOT/data}"' in unix
    assert 'export EMBER_DATA_DIR="${EMBER_DATA_DIR:-$ROOT/data}"' in unix_hosted
