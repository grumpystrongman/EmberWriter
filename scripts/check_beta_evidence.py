"""Evidence-based EmberWriter beta release gate.

The program cannot decide whether writing has artistic merit, so full-book
author/editor sign-off is mandatory. Never infer a pass from a generated text.
Usage: python scripts/check_beta_evidence.py <beta-evidence.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_WORDS = 60_000
MIN_CHAPTERS = 20


def evaluate(data: dict) -> list[str]:
    failures: list[str] = []
    source = data.get("candidate", {})
    if not source.get("commit") or not source.get("archive_sha256"):
        failures.append("Record the exact candidate commit and artifact SHA-256.")
    novel = data.get("novel", {})
    if novel.get("words", 0) < MIN_WORDS or novel.get("chapters", 0) < MIN_CHAPTERS:
        failures.append("Prove a completed, exported 60k+ word, 20+ chapter novel.")
    if not novel.get("every_chapter_author_approved") or not novel.get("epub_verified"):
        failures.append("All novel chapters require explicit author approval and EPUB verification.")
    if not novel.get("complete_human_read") or not novel.get("author_editor_quality_signoff"):
        failures.append("The full novel needs independent human reading and author/editor quality sign-off.")
    if novel.get("unresolved_major_prose_defects", 1) != 0:
        failures.append("Resolve major originality, repetition, continuity, or ending defects.")
    audiobook = data.get("audiobook", {})
    if audiobook.get("source_sha256") != novel.get("source_sha256") or not novel.get("source_sha256"):
        failures.append("Audiobook must match the human-approved novel edition fingerprint.")
    if audiobook.get("chapters", 0) != novel.get("chapters", -1):
        failures.append("Every approved manuscript chapter must have a corresponding audio chapter.")
    if not audiobook.get("all_chapters_proof_approved") or not audiobook.get("full_listen_completed"):
        failures.append("Require full author proof-listening and chapter approval.")
    if not audiobook.get("export_verified") or not audiobook.get("completeness_alignment_verified"):
        failures.append("Verify complete playable audiobook export and manuscript/audio completeness.")
    if not audiobook.get("licenses_reviewed") or audiobook.get("unresolved_major_audio_defects", 1) != 0:
        failures.append("Review narration rights and resolve major performance, omission, and audio defects.")
    install = data.get("install", {})
    for key, message in (
        ("fresh_windows_machine", "Verify installation on a fresh supported Windows machine."),
        ("first_run_launcher", "Verify the actual first-run installer and public launcher."),
        ("writer_without_ai", "Verify manuscript writing without models, GPU, or network."),
        ("data_survives_upgrade", "Verify existing manuscript and settings survive upgrade."),
        ("optional_models_explicit", "Confirm large optional models are author-selected."),
        ("relaunch_and_export", "Verify relaunch, project retention, and publication export."),
    ):
        if not install.get(key):
            failures.append(message)
    if not data.get("author_beta_release_signoff"):
        failures.append("Beta requires explicit release-owner sign-off after reviewing all evidence.")
    return failures


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_beta_evidence.py <beta-evidence.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print("BETA HOLD: evidence file missing. See docs/BETA_SHIP_GATES.md")
        return 1
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise TypeError("Evidence must be a JSON object")
    failures = evaluate(evidence)
    if failures:
        print(f"BETA HOLD: {len(failures)} unresolved acceptance requirements")
        for failure in failures:
            print(" - " + failure)
        return 1
    print("All recorded beta evidence gates satisfied. Verify signed artifacts before promotion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
