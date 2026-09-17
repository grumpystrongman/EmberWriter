from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
_LOG_DIR = _RUNTIME_DIR / "logs"
_STATUS_PATH = _RUNTIME_DIR / "writing-model-status.json"
_LOG_PATH = _LOG_DIR / "writing-model-install.log"

# Registry-native baseline: unlike hf.co shorthand, this does not depend on Ollama's
# Hugging Face proxy/import path. It is small enough for the machines that already run
# EmberWriter's 8B/14B local models and is purpose-built for creative/RP prose.
BASELINE_CREATIVE_MODEL = "HammerAI/rocinante-v1.1:12b-q4_K_M"
_CREATIVE_FAMILIES = (
    "cydonia",
    "rocinante",
    "magidonia",
    "magnum",
    "mag-mell",
    "mag_mell",
    "stheno",
    "pygmalion",
    "lunaris",
    "nemomix",
)

_STARTED = False
_START_LOCK = threading.Lock()


def _enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_INSTALL_CREATIVE_MODEL", "1").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def _write_status(**values: object) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        **values,
    }
    try:
        _STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _installed_model_names(ollama: str) -> list[str]:
    try:
        completed = subprocess.run(
            [ollama, "list"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) <= 1:
        return []
    return [line.split()[0] for line in lines[1:] if line.split()]


def has_creative_model(models: list[str]) -> bool:
    lowered = "\n".join(models).casefold()
    return any(family in lowered for family in _CREATIVE_FAMILIES)


def _worker() -> None:
    ollama = shutil.which("ollama")
    if not ollama:
        _write_status(state="unavailable", reason="ollama_not_on_path")
        return

    installed = _installed_model_names(ollama)
    if has_creative_model(installed):
        _write_status(state="ready", installed_models=installed, auto_installed=False)
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _write_status(
        state="installing",
        target_model=BASELINE_CREATIVE_MODEL,
        installed_models=installed,
        auto_installed=True,
    )

    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        with _LOG_PATH.open("ab") as log:
            completed = subprocess.run(
                [ollama, "pull", BASELINE_CREATIVE_MODEL],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=60 * 60 * 3,
                check=False,
                creationflags=flags,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        _write_status(
            state="failed",
            target_model=BASELINE_CREATIVE_MODEL,
            reason=f"{type(exc).__name__}: {exc}",
        )
        return

    installed = _installed_model_names(ollama)
    if completed.returncode == 0 and has_creative_model(installed):
        _write_status(
            state="ready",
            target_model=BASELINE_CREATIVE_MODEL,
            installed_models=installed,
            auto_installed=True,
        )
        return

    _write_status(
        state="failed",
        target_model=BASELINE_CREATIVE_MODEL,
        installed_models=installed,
        returncode=completed.returncode,
    )


def start_creative_model_provisioning() -> None:
    """Ensure a creative/RP-capable local model exists without blocking application startup."""

    global _STARTED
    if not _enabled():
        _write_status(state="disabled")
        return

    with _START_LOCK:
        if _STARTED:
            return
        _STARTED = True

    thread = threading.Thread(
        target=_worker,
        name="ember-writing-model-provisioner",
        daemon=True,
    )
    thread.start()
