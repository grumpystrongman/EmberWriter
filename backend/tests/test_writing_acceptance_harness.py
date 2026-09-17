from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "writing_acceptance.py"
SPEC = importlib.util.spec_from_file_location("writing_acceptance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_default_acceptance_prompt_exercises_hard_failure_contracts() -> None:
    prompt = MODULE.DEFAULT_PROMPT.casefold()
    assert "under 1300 words" in prompt
    assert "explicit" in prompt
    assert "penetration" in prompt
    assert "genitalia" in prompt
    assert "both participants reach orgasm" in prompt


def test_acceptance_result_never_contains_generated_prose_field() -> None:
    fields = set(MODULE.RunResult.__dataclass_fields__)
    assert "text" not in fields
    assert "prose" not in fields
    assert "output_sha256" in fields


def test_acceptance_threshold_defaults_to_ninety_percent(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["writing_acceptance.py"],
    )
    args = MODULE.parse_args()
    assert args.runs == 10
    assert args.required_pass_rate == 0.90
