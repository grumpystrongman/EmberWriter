"""Synthetic checks for the local question inventory audit."""
import importlib.util
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
