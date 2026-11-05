"""The beta gate must fail closed even when build/CI checks are green."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _gate():
    root = Path(__file__).resolve().parents[2]
    path = root / "scripts" / "check_beta_evidence.py"
    spec = importlib.util.spec_from_file_location("ember_beta_acceptance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_without_real_novel_and_audio_is_beta_hold():
    failures = _gate().evaluate({
        "candidate": {"commit": "test-only", "archive_sha256": "test-only"},
        "novel": {"words": 65000, "chapters": 24, "epub_verified": True},
        "audiobook": {"chapters": 2, "export_verified": True},
        "install": {"fresh_windows_machine": True},
    })
    assert any("full novel" in item.lower() or "human reading" in item.lower()
               for item in failures)
    assert any("audiobook" in item.lower() or "audio chapter" in item.lower()
               for item in failures)
    assert any("sign-off" in item.lower() for item in failures)


def test_all_evidence_gates_must_be_explicitly_satisfied():
    evidence = {
        "candidate": {"commit": "synthetic-test-commit", "archive_sha256": "synthetic-test-hash"},
        "novel": {
            "words": 72000, "chapters": 28, "source_sha256": "synthetic",
            "every_chapter_author_approved": True, "epub_verified": True,
            "complete_human_read": True, "author_editor_quality_signoff": True,
            "unresolved_major_prose_defects": 0,
        },
        "audiobook": {
            "chapters": 28, "source_sha256": "synthetic",
            "all_chapters_proof_approved": True, "full_listen_completed": True,
            "export_verified": True, "completeness_alignment_verified": True,
            "licenses_reviewed": True, "unresolved_major_audio_defects": 0,
        },
        "install": {
            "fresh_windows_machine": True, "first_run_launcher": True,
            "writer_without_ai": True, "data_survives_upgrade": True,
            "optional_models_explicit": True, "relaunch_and_export": True,
        },
        "author_beta_release_signoff": True,
    }
    assert _gate().evaluate(evidence) == []
    evidence["novel"]["complete_human_read"] = False
    assert any("human reading" in item.lower() for item in _gate().evaluate(evidence))
    evidence["novel"]["complete_human_read"] = True
    evidence["audiobook"]["source_sha256"] = "different"
    assert any("fingerprint" in item.lower() for item in _gate().evaluate(evidence))
