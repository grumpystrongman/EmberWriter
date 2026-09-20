from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from .writing_model_catalog import (
    ADULT_EXPLICIT_CANDIDATES,
    HIGH_HEAT_CYDONIA_24B,
    MAGNUM_V4_12B,
    PYGMALION_3_12B,
    adult_model_score,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
_LOG_DIR = _RUNTIME_DIR / "logs"
_STATUS_PATH = _RUNTIME_DIR / "writing-model-status.json"
_ACCEPTANCE_PATH = _RUNTIME_DIR / "writing-model-acceptance.json"
_BAKEOFF_PATH = _RUNTIME_DIR / "writing-model-bakeoff.json"
_LOG_PATH = _LOG_DIR / "writing-model-install.log"
_ACCEPTANCE_LOG_PATH = _LOG_DIR / "writing-model-acceptance.log"
_BAKEOFF_LOG_PATH = _LOG_DIR / "writing-model-bakeoff.log"

# Adult-fiction baseline. The model catalog keeps this replaceable so a future EmberWriter-owned
# tune can take over the capability slot without changing Studio or project files.
BASELINE_CREATIVE_MODEL = PYGMALION_3_12B
# Optional escalation tier for machines with substantially more local memory.
HIGH_HEAT_CREATIVE_MODEL = HIGH_HEAT_CYDONIA_24B
_MIN_HIGH_HEAT_FREE_BYTES = 22 * 1024**3
_MIN_CHALLENGER_FREE_BYTES = 10 * 1024**3
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
    return adult_model_score(model)


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


def _cached_bakeoff_winner(installed: list[str]) -> str | None:
    try:
        payload = json.loads(_BAKEOFF_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("acceptance_version") != _ACCEPTANCE_VERSION or payload.get("passed") is not True:
        return None
    requested = {str(value).casefold() for value in payload.get("models", []) if value}
    required = {value.casefold() for value in ADULT_EXPLICIT_CANDIDATES}
    if requested != required:
        return None
    winner = str(payload.get("best_model", "")).strip()
    installed_by_name = {item.casefold(): item for item in installed}
    return installed_by_name.get(winner.casefold()) if winner else None


def _run_bakeoff(installed: list[str], auto_installed: bool) -> str | None:
    installed_by_name = {item.casefold(): item for item in installed}
    candidates = [
        installed_by_name.get(candidate.casefold())
        for candidate in ADULT_EXPLICIT_CANDIDATES
    ]
    if any(not candidate for candidate in candidates):
        return None

    cached = _cached_bakeoff_winner(installed)
    if cached:
        _write_status(
            state="ready",
            installed_models=installed,
            auto_installed=auto_installed,
            acceptance_state="passed",
            bakeoff_state="passed",
            adult_model=cached,
            bakeoff_cached=True,
        )
        return cached

    if not _acceptance_enabled():
        return None

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="testing",
        bakeoff_state="testing",
        bakeoff_models=candidates,
    )

    env = os.environ.copy()
    env["EMBER_AUTO_INSTALL_CREATIVE_MODEL"] = "0"
    env["EMBER_AUTO_TEST_CREATIVE_MODEL"] = "0"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    command = [
        sys.executable,
        "-m",
        "app.model_acceptance",
        "--bakeoff",
        "--attempts",
        "3",
    ]
    for candidate in candidates:
        command.extend(["--model", str(candidate)])

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
            bakeoff_reason=f"{type(exc).__name__}: {exc}",
        )
        return None

    winner = _cached_bakeoff_winner(installed) if completed.returncode == 0 else None
    _write_status(
        state="ready",
        installed_models=installed,
        auto_installed=auto_installed,
        acceptance_state="passed" if winner else "failed",
        bakeoff_state="passed" if winner else "failed",
        adult_model=winner or "",
        bakeoff_cached=False,
        bakeoff_returncode=completed.returncode,
    )
    return winner


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


def _can_install_challenger() -> bool:
    try:
        return shutil.disk_usage(_REPO_ROOT).free >= _MIN_CHALLENGER_FREE_BYTES
    except OSError:
        return False


def _can_install_high_heat() -> bool:
    if not _high_heat_escalation_enabled():
        return False
    try:
        return shutil.disk_usage(_REPO_ROOT).free >= _MIN_HIGH_HEAT_FREE_BYTES
    except OSError:
        return False


def _ready(ollama: str, installed: list[str], auto_installed: bool) -> None:
    installed_by_name = {item.casefold(): item for item in installed}
    pygmalion = installed_by_name.get(PYGMALION_3_12B.casefold())
    magnum = installed_by_name.get(MAGNUM_V4_12B.casefold())

    # When disk permits, install both 12B candidates and compare them under the exact same
    # EmberWriter delivery contract. This is the normal commercial/product path.
    if pygmalion and not magnum and _can_install_challenger():
        _write_status(
            state="installing",
            target_model=MAGNUM_V4_12B,
            installed_models=installed,
            auto_installed=True,
            bakeoff_state="installing_challenger",
        )
        if _pull_model(ollama, MAGNUM_V4_12B):
            installed = _installed_model_names(ollama)
            installed_by_name = {item.casefold(): item for item in installed}
            magnum = installed_by_name.get(MAGNUM_V4_12B.casefold())

    if pygmalion and magnum:
        winner = _run_bakeoff(installed, auto_installed=auto_installed)
        if winner:
            return

    # Degrade gracefully on constrained machines: validate the best installed adult model.
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

    # Only escalate to the much heavier 24B tier after the 12B capability slot has failed.
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
            escalation_reason="12B adult candidates failed; 24B fallback requires at least 22GB free or escalation is disabled",
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
    _run_acceptance(HIGH_HEAT_CREATIVE_MODEL, upgraded, auto_installed=True)


def _worker() -> None:
    ollama = shutil.which("ollama")
    if not ollama:
        _write_status(state="unavailable", reason="ollama_not_on_path")
        return

    installed = _installed_model_names(ollama)
    baseline_present = any(
        item.casefold() == BASELINE_CREATIVE_MODEL.casefold()
        for item in installed
    )
    if baseline_present:
        _ready(ollama, installed, auto_installed=False)
        return

    # Existing generic/RP models no longer suppress provisioning of the dedicated adult slot.
    # This lets old EmberWriter installs migrate from Rocinante/Qwen without deleting them.
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
    if any(item.casefold() == BASELINE_CREATIVE_MODEL.casefold() for item in installed):
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
