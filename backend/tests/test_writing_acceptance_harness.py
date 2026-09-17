from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "writing_acceptance.py"


def test_acceptance_harness_help_is_runnable() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0
    assert "--runs" in completed.stdout
    assert "--required-pass-rate" in completed.stdout
    assert "--prompt-file" in completed.stdout


def test_default_acceptance_contract_is_encoded_without_saved_prose() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "under 1300 words" in source
    assert "penetration/genitalia" in source
    assert "both participants reach orgasm" in source
    assert 'default=10' in source
    assert 'default=0.90' in source
    assert 'output_sha256' in source
    assert 'Generated manuscript prose is intentionally neither printed nor stored.' in source
