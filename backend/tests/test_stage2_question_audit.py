"""Synthetic checks for the local question inventory audit."""
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "audit_stage2_questions", Path(__file__).resolve().parents[2] / "scripts" / "audit_stage2_questions.py"
)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def test_inventory_deduplicates_and_excludes_synthetic_and_unreferenced():
    result = audit_module.audit([
        {"question": "Where is the key?", "origin": "synthetic"},
        {"question": "WHERE is the key!", "origin": "author_reviewed", "review_reference": "r1"},
        {"question": "Who knows?", "origin": "author_reviewed"},
        {"question": "When revealed?", "origin": "author_reviewed", "review_reference": "r2"},
    ])
    assert result["distinct_text"] == 3
    assert result["duplicate_rows"] == [2]
    assert result["claimed_reviewed_distinct"] == 1
    assert result["human_review_independently_verified"] is False


def test_inventory_rejects_empty_question():
    with pytest.raises(ValueError):
        audit_module.audit([{"question": "!?"}])


def test_cli_consumes_piped_json_without_opening_a_user_path(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["audit_stage2_questions.py"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([
        {"question": "Who saw the letter?", "origin": "synthetic"},
    ])))
    audit_module.main()
    assert json.loads(capsys.readouterr().out)["distinct_text"] == 1


def test_cli_rejects_untrusted_path_argument(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["audit_stage2_questions.py", "../../secrets.json"])
    with pytest.raises(SystemExit, match="pipe a local JSON inventory"):
        audit_module.main()


def test_cli_rejects_non_array_input(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["audit_stage2_questions.py"])
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"question": "not a list"}'))
    with pytest.raises(ValueError, match="JSON array"):
        audit_module.main()
