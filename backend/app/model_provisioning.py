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
_BAKEOFF_PATH = _RUNTIME_DIR / "model-bakeoff.json"
_BAKEOFF_LOG_PATH = _LOG_DIR / "model-bakeoff.log"

# Registry-native baseline: compact enough for machines that already run EmberWriter's
# 8B/14B local models and purpose-built for creative/RP prose.
BASELINE_CREATIVE_MODEL = "hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M"
# Escalation tier for authors whose direct-adult acceptance contract defeats the lighter model.
# This Ollama package is a Q4_K_M Heretic/decensored Cydonia build (~15 GB download footprint).
HIGH_HEAT_CREATIVE_MODEL = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"
_ADULT_BAKEOFF_MODELS = (
    "hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M",
    "hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M",
    "R4C3R/qwen3-8b-heretic:q4_k_m",
)
_MIN_HIGH_HEAT_FREE_BYTES = 22 * 1024**3
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
_ACCEPTANCE_VERSION = 3

_STARTED = False
_START_LOCK = threading.Lock()


def _enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_INSTALL_CREATIVE_MODEL", "1").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def _acceptance_enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_TEST_CREATIVE_MODEL", "1").strip().casefold()
    return raw not in {"0", "false", "no", "off"}


def _high_heat_escalation_enabled() -> bool:
    raw = os.getenv("EMBER_AUTO_INSTALL_HIGH_HEAT_MODEL", "1").strip().casefold()
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
        return 300
    if "rocinante-x" in name and any(token in name for token in ("heretic", "abliter", "decensor")):
        return 290
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



def _cached_bakeoff_winner(installed: list[str]) -> str:
    try:
        payload = json.loads(_BAKEOFF_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict) or payload.get("acceptance_version") != _ACCEPTANCE_VERSION:
        return ""
    winner = str(payload.get("winner") or "").strip()
    if not winner:
        return ""
    by_name = {item.casefold(): item for item in installed}
    return by_name.get(winner.casefold(), "")


def _run_adult_bakeoff(installed: list[str], auto_installed: bool) -> str:
    installed_names = {item.casefold() for item in installed}
    available = [model for model in _ADULT_BAKEOFF_MODELS if model.casefold() in installed_names]
    if not available or not _acceptance_enabled():
        return ""

    cached = _cached_bakeoff_winner(installed)
    if cached:
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="passed",
            acceptance_model=cached,
            bakeoff_state="cached",
        )
        return cached

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="testing",
        bakeoff_state="testing",
        bakeoff_models=available,
    )

    env = os.environ.copy()
    env["EMBER_AUTO_INSTALL_CREATIVE_MODEL"] = "0"
    env["EMBER_AUTO_TEST_CREATIVE_MODEL"] = "0"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    command = [sys.executable, "-m", "app.model_bakeoff", "--attempts", "3"]
    for model in available:
        command.extend(["--model", model])

    try:
        with _BAKEOFF_LOG_PATH.open("ab") as log:
            completed = subprocess.run(
                command,
                cwd=str(_REPO_ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=60 * 60 * 4,
                check=False,
                creationflags=flags,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="failed",
            bakeoff_state="failed",
            acceptance_reason=f"{type(exc).__name__}: {exc}",
        )
        return ""

    winner = _cached_bakeoff_winner(installed)
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="passed" if winner else "failed",
        acceptance_model=winner or None,
        bakeoff_state="passed" if winner else "failed",
        bakeoff_returncode=completed.returncode,
    )
    return winner


def _run_acceptance(model: str, installed: list[str], auto_installed: bool) -> bool:
    if not _acceptance_enabled():
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="disabled",
        )
        return True

    if _cached_acceptance_passed(model):
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="passed",
            acceptance_model=model,
            acceptance_cached=True,
        )
        return True

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
        return False

    passed = completed.returncode == 0
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="passed" if passed else "failed",
        acceptance_model=model,
        acceptance_cached=False,
        acceptance_returncode=completed.returncode,
    )
    return passed


def _pull_model(ollama: str, model: str) -> bool:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        with _LOG_PATH.open("ab") as log:
            completed = subprocess.run(
                [ollama, "pull", model],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=60 * 60 * 4,
                check=False,
                creationflags=flags,
            )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _can_install_high_heat() -> bool:
    if not _high_heat_escalation_enabled():
        return False
    try:
        return shutil.disk_usage(_REPO_ROOT).free >= _MIN_HIGH_HEAT_FREE_BYTES
    except OSError:
        return False


def _ready(ollama: str, installed: list[str], auto_installed: bool) -> None:
    if _run_adult_bakeoff(installed, auto_installed):
        return

    model = _best_creative_model(installed)
    if not model:
        _write_status(
            state="failed",
            installed_models=installed,
            auto_installed=auto_installed,
            reason="creative_model_not_resolved",
        )
        return

    if _run_acceptance(model, installed, auto_installed):
        return

    high_heat_present = any(HIGH_HEAT_CREATIVE_MODEL.casefold() == item.casefold() for item in installed)
    if high_heat_present or model.casefold() == HIGH_HEAT_CREATIVE_MODEL.casefold():
        return
    if not _can_install_high_heat():
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="failed",
            acceptance_model=model,
            escalation_state="not_available",
            escalation_reason="high_heat_model_requires_at_least_22GB_free_or_escalation_is_disabled",
        )
        return

    _write_status(
        state="installing",
        target_model=HIGH_HEAT_CREATIVE_MODEL,
        installed_models=installed,
        auto_installed=True,
        acceptance_state="failed",
        acceptance_model=model,
        escalation_state="installing_high_heat_model",
    )
    if not _pull_model(ollama, HIGH_HEAT_CREATIVE_MODEL):
        _write_status(
            state="ready",
            installed_models=_installed_model_names(ollama),
            auto_installed=auto_installed,
            acceptance_state="failed",
            acceptance_model=model,
            escalation_state="install_failed",
        )
        return

    upgraded = _installed_model_names(ollama)
    upgraded_model = _best_creative_model(upgraded)
    if not upgraded_model:
        _write_status(
            state="failed",
            installed_models=upgraded,
            reason="high_heat_model_installed_but_not_resolved",
        )
        return
    _run_acceptance(upgraded_model, upgraded, auto_installed=True)


def _worker() -> None:
    ollama = shutil.which("ollama")
    if not ollama:
        _write_status(state="unavailable", reason="ollama_not_on_path")
        return

    installed = _installed_model_names(ollama)
    if has_creative_model(installed):
        _ready(ollama, installed, auto_installed=False)
        return

    _write_status(
        state="installing",
        target_model=BASELINE_CREATIVE_MODEL,
        installed_models=installed,
        auto_installed=True,
    )
    if not _pull_model(ollama, BASELINE_CREATIVE_MODEL):
        _write_status(
            state="failed",
            target_model=BASELINE_CREATIVE_MODEL,
            installed_models=_installed_model_names(ollama),
            reason="baseline_model_install_failed",
        )
        return

    installed = _installed_model_names(ollama)
    if has_creative_model(installed):
        _ready(ollama, installed, auto_installed=True)
        return

    _write_status(
        state="failed",
        target_model=BASELINE_CREATIVE_MODEL,
        installed_models=installed,
        reason="baseline_model_install_completed_but_model_not_resolved",
    )


def start_creative_model_provisioning() -> None:
    """Ensure, acceptance-test, and if needed escalate a creative/RP-capable local model."""

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
