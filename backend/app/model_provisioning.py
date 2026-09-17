from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
_LOG_DIR = _RUNTIME_DIR / "logs"
_STATUS_PATH = _RUNTIME_DIR / "writing-model-status.json"
_ACCEPTANCE_PATH = _RUNTIME_DIR / "writing-model-acceptance.json"
_LOG_PATH = _LOG_DIR / "writing-model-install.log"
_ACCEPTANCE_LOG_PATH = _LOG_DIR / "writing-model-acceptance.log"

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
_ACCEPTANCE_VERSION = 1

_STARTED = False
_START_LOCK = threading.Lock()


def _enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_INSTALL_CREATIVE_MODEL", "1").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def _acceptance_enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_TEST_CREATIVE_MODEL", "1").strip().casefold()
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


def _creative_model_score(model: str) -> int:
    name = model.casefold()
    if "cydonia" in name and any(token in name for token in ("heretic", "abliter", "decensor")):
        return 280
    if "rocinante-x" in name:
        return 270
    if "rocinante" in name:
        return 260
    if any(token in name for token in ("magidonia", "magnum", "mag-mell", "mag_mell")):
        return 245
    if "cydonia" in name:
        return 235
    if any(token in name for token in ("stheno", "pygmalion", "lunaris", "nemomix")):
        return 220
    return 0


def _best_creative_model(models: list[str]) -> str | None:
    ranked = sorted(models, key=_creative_model_score, reverse=True)
    if not ranked or _creative_model_score(ranked[0]) <= 0:
        return None
    return ranked[0]


def _cached_acceptance_passed(model: str) -> bool:
    try:
        payload = json.loads(_ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("acceptance_version") != _ACCEPTANCE_VERSION:
        return False
    if payload.get("passed") is not True:
        return False
    requested = str(payload.get("requested_model", "")).casefold()
    effective = [str(value).casefold() for value in payload.get("effective_models", []) if value]
    target = model.casefold()
    return requested == target or target in effective


def _run_acceptance(model: str, installed: list[str], auto_installed: bool) -> None:
    if not _acceptance_enabled():
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="disabled",
        )
        return

    if _cached_acceptance_passed(model):
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="passed",
            acceptance_model=model,
            acceptance_cached=True,
        )
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="testing",
        acceptance_model=model,
    )

    env = os.environ.copy()
    # Importing app.model_acceptance imports app.__init__; disable provisioning in the child
    # so the acceptance subprocess cannot recursively start another installer/tester.
    env["EMBER_AUTO_INSTALL_CREATIVE_MODEL"] = "0"
    env["EMBER_AUTO_TEST_CREATIVE_MODEL"] = "0"

    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        with _ACCEPTANCE_LOG_PATH.open("ab") as log:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.model_acceptance",
                    "--model",
                    model,
                    "--attempts",
                    "3",
                ],
                cwd=str(_REPO_ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=60 * 60 * 2,
                check=False,
                creationflags=flags,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="failed",
            acceptance_model=model,
            acceptance_reason=f"{type(exc).__name__}: {exc}",
        )
        return

    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="passed" if completed.returncode == 0 else "failed",
        acceptance_model=model,
        acceptance_cached=False,
        acceptance_returncode=completed.returncode,
    )


def _ready(installed: list[str], auto_installed: bool) -> None:
    model = _best_creative_model(installed)
    if not model:
        _write_status(
            state="failed",
            installed_models=installed,
            auto_installed=auto_installed,
            reason="creative_model_not_resolved",
        )
        return
    _run_acceptance(model, installed, auto_installed)


def _worker() -> None:
    ollama = shutil.which("ollama")
    if not ollama:
        _write_status(state="unavailable", reason="ollama_not_on_path")
        return

    installed = _installed_model_names(ollama)
    if has_creative_model(installed):
        _ready(installed, auto_installed=False)
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
        _ready(installed, auto_installed=True)
        return

    _write_status(
        state="failed",
        target_model=BASELINE_CREATIVE_MODEL,
        installed_models=installed,
        returncode=completed.returncode,
    )


def start_creative_model_provisioning() -> None:
    """Ensure, then acceptance-test, a creative/RP-capable local model without blocking startup."""

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
