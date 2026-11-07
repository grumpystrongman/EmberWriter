"""Fail-closed, file-backed checks for an author-approved public beta.

Never turn synthetic tests, an AI self-assessment, or a video preview into
author/editor sign-off. This validates artifacts and explicit attestations;
artistic merit and real human participation require independent confirmation.

Usage:
  python scripts/qualify_release.py path/to/release-evidence.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import wave
import zipfile
from datetime import date
from pathlib import Path

CHAPTER_MIN = 20
WORD_MIN = 60_000
AUDIO_MIN_SECONDS = 4 * 3600
REQUIRED_INSTALL = (
    "fresh_windows_machine",
    "writer_without_ai",
    "pinokio_launcher",
    "fresh_install",
    "data_survives_upgrade",
    "safe_uninstall",
    "backup_restore_drill",
    "offline_open",
    "optional_models_explicit",
    "relaunch_and_export",
)
SHA_RE = re.compile(r"[a-f0-9]{64}", re.IGNORECASE)
COMMIT_RE = re.compile(r"[a-f0-9]{40}", re.IGNORECASE)


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_file(base: Path, value: object, expected: object,
                 errors: list[str], label: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: an existing artifact path is required")
        return None
    path = (base / value).resolve()
    if not path.is_file():
        errors.append(f"{label}: artifact missing")
        return None
    if not isinstance(expected, str) or not SHA_RE.fullmatch(expected):
        errors.append(f"{label}: invalid SHA-256")
        return None
    if _digest(path) != expected.casefold():
        errors.append(f"{label}: byte-for-byte digest mismatch")
        return None
    return path


def _attested(record: object, expected_sha: str, errors: list[str],
              label: str, *, required_role: str = "") -> None:
    if not isinstance(record, dict):
        errors.append(f"{label}: independent human review is required")
        return
    if record.get("synthetic") or record.get("automated") or record.get("ai_reviewer"):
        errors.append(f"{label}: simulated or automated review cannot sign off")
    if not isinstance(record.get("reviewer"), str) or len(record["reviewer"].strip()) < 4:
        errors.append(f"{label}: named human reviewer is missing")
    if required_role and record.get("role") != required_role:
        errors.append(f"{label}: requires {required_role} reviewer")
    if record.get("source_sha256") != expected_sha:
        errors.append(f"{label}: review does not match the edition fingerprint")
    if not isinstance(record.get("assessment"), str) or len(record["assessment"].strip()) < 100:
        errors.append(f"{label}: detailed written assessment is required")
    try:
        reviewed_at = date.fromisoformat(str(record["reviewed_at"]))
        if reviewed_at > date.today():
            raise ValueError("future date")
    except (ValueError, KeyError):
        errors.append(f"{label}: valid completed review date is required")
    if record.get("approved") is not True:
        errors.append(f"{label}: explicit human approval is missing")


def evaluate(evidence: dict, base: Path) -> list[str]:
    errors: list[str] = []
    if evidence.get("schema_version") != 1:
        errors.append("Use release-qualification evidence schema v1")
    if evidence.get("synthetic") or evidence.get("kind") != "production_candidate":
        errors.append("Synthetic QA fixtures are not qualifying release evidence")

    candidate = evidence.get("candidate", {})
    if not isinstance(candidate, dict):
        candidate = {}
    commit = candidate.get("commit")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        errors.append("Candidate must name an exact 40-digit Git commit")
    artifact = _verify_file(
        base, candidate.get("source_archive"), candidate.get("archive_sha256"),
        errors, "candidate archive",
    )
    if artifact and artifact.suffix.casefold() != ".zip":
        errors.append("Candidate source archive must be a ZIP file")

    novel = evidence.get("novel", {})
    if not isinstance(novel, dict):
        novel = {}
    entries = novel.get("chapters", [])
    if not isinstance(entries, list) or len(entries) < CHAPTER_MIN:
        errors.append("Novel needs at least 20 approved source chapters")
        entries = []
    if len(entries) > 120:
        errors.append("Novel exceeds supported chapter count")
        entries = entries[:120]
    sources: list[tuple[Path, str, int]] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or entry.get("number") != index:
            errors.append(f"Novel chapter {index}: chapter ordering is invalid")
            continue
        path = _verify_file(
            base, entry.get("path"), entry.get("sha256"),
            errors, f"novel chapter {index}",
        )
        if entry.get("author_approved") is not True:
            errors.append(f"Novel chapter {index}: explicitly author-approved source required")
        if path:
            if path.suffix.casefold() not in {".md", ".txt"}:
                errors.append(f"Novel chapter {index}: source must be Markdown or text")
            try:
                content = path.read_text(encoding="utf-8")
                count = len(re.findall(r"\b[\w]+(?:['-][\w]+)*\b", content))
                sources.append((path, entry["sha256"], count))
                if count < 500:
                    errors.append(f"Novel chapter {index}: not a substantive chapter")
            except UnicodeError:
                errors.append(f"Novel chapter {index}: invalid UTF-8")
    total_words = sum(count for _path, _sha, count in sources)
    if total_words < WORD_MIN:
        errors.append(f"Novel has {total_words} verified words; at least 60,000 required")
    if novel.get("word_count") != total_words:
        errors.append("Novel claimed word count differs from verified manuscript files")
    if len(sources) != len(entries):
        errors.append("Novel source chapter evidence is incomplete")
    joined_fingerprint = hashlib.sha256(
        "\n".join(sha for _path, sha, _count in sources).encode("ascii")
    ).hexdigest()
    if novel.get("source_sha256") != joined_fingerprint:
        errors.append("Novel whole-edition fingerprint does not match ordered chapter sources")
    epub_path = _verify_file(base, novel.get("epub_path"),
                             novel.get("epub_sha256"), errors, "novel EPUB")
    docx_path = _verify_file(base, novel.get("docx_path"),
                             novel.get("docx_sha256"), errors, "novel DOCX")
    if epub_path:
        try:
            with zipfile.ZipFile(epub_path) as archive:
                contents = [item for item in archive.namelist()
                            if re.search(r"chapter-\d+\.xhtml$", item)]
                if len(contents) != len(entries):
                    errors.append("EPUB chapter count does not match source manuscript")
                if not archive.testzip() is None:
                    errors.append("EPUB container contains damaged entries")
        except (OSError, zipfile.BadZipFile):
            errors.append("EPUB is not a valid readable archive")
    if docx_path:
        try:
            with zipfile.ZipFile(docx_path) as archive:
                if "word/document.xml" not in archive.namelist():
                    errors.append("DOCX manuscript body is missing")
                if archive.testzip() is not None:
                    errors.append("DOCX container failed its integrity test")
        except (OSError, zipfile.BadZipFile):
            errors.append("DOCX is not a valid readable document")
    _attested(novel.get("author_review"), joined_fingerprint, errors,
              "novel author review", required_role="author")
    _attested(novel.get("editor_review"), joined_fingerprint, errors,
              "novel editor review", required_role="editor")
    if novel.get("unresolved_major_defects") != 0:
        errors.append("Novel still has unresolved major continuity or prose defects")

    audiobook = evidence.get("audiobook", {})
    if not isinstance(audiobook, dict):
        audiobook = {}
    if audiobook.get("source_sha256") != joined_fingerprint:
        errors.append("Audiobook proof does not match approved novel fingerprint")
    takes = audiobook.get("chapters", [])
    if not isinstance(takes, list) or len(takes) != len(entries):
        errors.append("Audiobook chapter inventory does not match source edition")
        takes = []
    total_audio_seconds = 0.0
    for index, take in enumerate(takes, 1):
        if not isinstance(take, dict):
            errors.append(f"Audio chapter {index}: invalid proof record")
            continue
        if take.get("number") != index:
            errors.append(f"Audio chapter {index}: wrong chapter order")
        expected = sources[index - 1][1] if index <= len(sources) else ""
        if take.get("source_sha256") != expected:
            errors.append(f"Audio chapter {index}: stale manuscript source")
        wav = _verify_file(base, take.get("wav_path"), take.get("wav_sha256"),
                           errors, f"audio chapter {index}")
        if wav:
            try:
                with wave.open(str(wav), "rb") as recording:
                    if recording.getnframes() == 0 or recording.getframerate() < 16000:
                        raise ValueError("empty or unsupported audio")
                    seconds = recording.getnframes() / recording.getframerate()
                    total_audio_seconds += seconds
            except (wave.Error, EOFError, OSError, ValueError):
                errors.append(f"Audio chapter {index}: unplayable or empty WAV")
        if take.get("author_proof_approved") is not True or not take.get("proof_reviewer"):
            errors.append(f"Audio chapter {index}: author listening approval missing")
        if take.get("synthetic") or take.get("mocked_voice"):
            errors.append(f"Audio chapter {index}: mocked speech is not release audio")
    if total_audio_seconds < AUDIO_MIN_SECONDS:
        errors.append("Complete audiobook is too short to represent a 60k-word recording")
    if audiobook.get("full_listen_completed") is not True:
        errors.append("Audiobook requires full end-to-end human listening")
    _attested(audiobook.get("human_proof"), joined_fingerprint, errors,
              "audiobook human proof")
    _verify_file(base, audiobook.get("final_m4b_path"),
                 audiobook.get("final_m4b_sha256"), errors, "final M4B")
    if audiobook.get("rights_reviewed") is not True:
        errors.append("Narrator/model rights and distribution terms need review")
    if audiobook.get("unresolved_major_defects") != 0:
        errors.append("Audiobook contains unresolved major defects")

    installation = evidence.get("installation", {})
    if not isinstance(installation, dict):
        installation = {}
    for key in REQUIRED_INSTALL:
        if installation.get(key) is not True:
            errors.append(f"Installation acceptance missing: {key}")
    if installation.get("synthetic") or installation.get("reused_developer_machine"):
        errors.append("Install must be performed on a fresh supported Windows environment")
    _verify_file(base, installation.get("test_log_path"),
                 installation.get("test_log_sha256"), errors, "fresh-install test log")
    _attested(installation.get("human_review"), joined_fingerprint, errors,
              "independent installation acceptance")

    _attested(evidence.get("release_owner_approval"), joined_fingerprint, errors,
              "release owner final signoff", required_role="author")
    if errors:
        return sorted(set(errors))
    return []


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: python scripts/qualify_release.py release-evidence.json")
        return 2
    path = Path(args[0]).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Evidence must be a JSON object")
        failures = evaluate(data, path.parent)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"RELEASE HOLD: unreadable or invalid evidence: {exc}")
        return 1
    if failures:
        print(f"RELEASE HOLD: {len(failures)} unmet criteria")
        for item in failures:
            print(" - " + item)
        return 1
    print("Release evidence mechanically validated. Human authenticity and final review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
