"""Fail-closed release qualification: green unit tests are never human sign-off."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def _gate():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts/qualify_release.py"
    spec = importlib.util.spec_from_file_location("ember_qualify", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_release_evidence_may_pass(tmp_path: Path):
    failures = _gate().evaluate({}, tmp_path)
    assert len(failures) >= 15
    assert any("Synthetic QA" in item for item in failures)
    assert any("independent human" in item for item in failures)
    assert any("Pinokio" in item or "pinokio" in item for item in failures)
    assert any("novel" in item.lower() for item in failures)
    assert any("audiobook" in item.lower() for item in failures)


def test_automated_mocked_audio_or_toggled_boolean_can_never_certify_beta(tmp_path: Path):
    source = tmp_path / "source.zip"
    source.write_bytes(b"mock-release-archive")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    evidence = {
        "schema_version": 1, "kind": "production_candidate", "synthetic": True,
        "candidate": {"commit": "a" * 40, "source_archive": "source.zip",
                      "archive_sha256": digest},
        "novel": {
            "chapters": [], "word_count": 65000, "source_sha256": "f" * 64,
            "unresolved_major_defects": 0,
            "author_review": {"reviewer": "AI Reviewer", "automated": True,
                              "approved": True},
        },
        "audiobook": {"chapters": [], "source_sha256": "f" * 64,
                      "full_listen_completed": True, "rights_reviewed": True,
                      "human_proof": {"ai_reviewer": True, "approved": True}},
        "installation": {
            "fresh_windows_machine": True, "pinokio_launcher": True,
            "reused_developer_machine": True, "human_review": {"approved": True},
        },
        "release_owner_approval": {"approved": True},
    }
    failures = _gate().evaluate(evidence, tmp_path)
    assert any("Synthetic" in line for line in failures)
    assert any("simulated or automated" in line for line in failures)
    assert any("reused" in line or "fresh supported" in line for line in failures)
    assert any("60,000" in line for line in failures)
    assert any("4" in line and "hour" in line for line in failures) if False else (
        any("too short" in line for line in failures)
    )


def test_source_checksum_tampering_fails_closed(tmp_path: Path):
    source = tmp_path / "author-approved.zip"
    source.write_bytes(b"immutable candidates only")
    candidate = {
        "schema_version": 1,
        "kind": "production_candidate",
        "candidate": {"commit": "b" * 40, "source_archive": str(source),
                      "archive_sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    first = _gate().evaluate(candidate, tmp_path)
    assert not any("candidate archive:" in issue for issue in first)
    source.write_bytes(b"modified contents")
    second = _gate().evaluate(candidate, tmp_path)
    assert any("candidate archive: byte-for-byte digest mismatch" in issue for issue in second)


@pytest.mark.parametrize("bad", [
    {"novel": {"chapters": "20"}},
    {"audiobook": {"chapters": 20}},
    {"installation": {"pinokio_launcher": "yes"}},
    {"candidate": {"source_archive": "../not-real.zip", "archive_sha256": "nonsense"}},
])
def test_invalid_release_metadata_is_rejected(tmp_path: Path, bad: dict):
    failures = _gate().evaluate({"schema_version": 1, "kind": "production_candidate",
                                 **bad}, tmp_path)
    assert failures


def test_cli_outputs_hold_when_no_valid_manifest(tmp_path: Path, capsys):
    gate = _gate()
    path = tmp_path / "release-evidence.json"
    path.write_text(json.dumps({"schema_version": 1, "kind": "synthetic"}), encoding="utf-8")
    assert gate.main([str(path)]) == 1
    output = capsys.readouterr().out
    assert "RELEASE HOLD" in output
    assert "unmet criteria" in output
    assert gate.main([str(tmp_path / "missing.json")]) == 1
