"""Part 3: locally derived editorial diagnostics and safe author-controlled edits.

Measurements describe evidence, not literary quality. There is no generative
inference, external request, or automatic approval of textual changes.
"""
from __future__ import annotations

import difflib
import hashlib
import re
import threading

from . import manuscript_intelligence as intelligence
from . import revisions
from .storage import get_project, read_text, save_text

_LOCK = threading.RLock()
MAX_DOCUMENT_BYTES = 1_500_000
WORD = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")
PARAGRAPH = re.compile(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*")
DIALOGUE = re.compile(r'[“"][^”"\n]{2,}[”"]')
BEAT_PATTERN = re.compile(r"\b(?:but|however|until|suddenly|then|because|instead|yet)\b", re.IGNORECASE)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_editable(slug: str, path: str) -> bool:
    project = get_project(slug)
    return (
        isinstance(path, str)
        and path.startswith("manuscript/")
        and path.lower().endswith((".md", ".txt"))
        and path in project["files"]
        and not path.startswith("manuscript/book-studio/")
    )


def chapters_report(slug: str, subjects: list[str] | None = None) -> dict:
    report = intelligence.analyze(slug, subjects)
    chapters = report["chapters"]
    counts = [chapter["words"] for chapter in chapters]
    maximum = max(counts, default=1)
    normalized = []
    for item in chapters:
        avg_sentence = item["average_sentence_words"]
        flags = []
        if item["path"] in report["short_chapters"]:
            flags.append({"kind": "length", "label": "Brief relative to this book",
                          "evidence": f"{item['words']} words vs {report['average_chapter_words']} average"})
        if item["path"] in report["long_chapters"]:
            flags.append({"kind": "length", "label": "Long relative to this book",
                          "evidence": f"{item['words']} words vs {report['average_chapter_words']} average"})
        if avg_sentence >= 27:
            flags.append({"kind": "rhythm", "label": "Longer average sentences",
                          "evidence": f"{avg_sentence} words per sentence"})
        if item["mechanical_flags"] > 0:
            flags.append({"kind": "mechanics", "label": "Review mechanical findings",
                          "evidence": f"{item['mechanical_flags']} mechanical flags"})
        editable = _is_editable(slug, item["path"])
        prompts = []
        if editable:
            source = read_text(slug, item["path"])
            pieces = [
                (segment.strip(), source.find(segment)) for segment in re.split(r"\n\s*\n", source)
                if segment.strip() and not segment.strip().startswith("#")
            ]
            if pieces:
                opening, start = pieces[0]
                ending, end_start = pieces[-1]
                for category, label, question, quote, offset in [
                    ("opening", "Opening contract",
                     "What dramatic question or immediate desire does this opening establish?",
                     opening[:220], start),
                    ("aftermath", "Ending consequence",
                     "What decision, revelation, or relationship change should carry into the next chapter?",
                     ending[-220:], end_start + max(0, len(ending) - 220)),
                ]:
                    prompts.append({
                        "kind": category, "label": label, "question": question,
                        "quote": quote, "line": source.count("\n", 0, max(0, offset)) + 1,
                        "path": item["path"],
                    })
                dialogue = DIALOGUE.search(source)
                if dialogue:
                    prompts.append({
                        "kind": "dialogue", "label": "Dialogue identity",
                        "question": "Are the speaker's diction, objectives, and silences distinguishable?",
                        "quote": dialogue.group()[:180],
                        "line": source.count("\n", 0, dialogue.start()) + 1,
                        "path": item["path"],
                    })
        normalized.append({
            **item, "word_share": round(item["words"] / max(maximum, 1), 4),
            "diagnostics": flags,
            "review_prompts": prompts,
            "editable": editable,
            "title": (re.search(r"(?m)^#\s+(.+)", source).group(1)[:160]
                      if editable and re.search(r"(?m)^#\s+(.+)", source)
                      else item["title"]),
        })
    subject_names = report["subject_names"]
    presence = []
    for subject in subject_names:
        presence.append({
            "name": subject,
            "chapters": [{
                "path": chapter["path"], "title": chapter["title"], "index": chapter["index"],
                "evidence": next((mention["evidence"] for mention in chapter["tracked_subjects"]
                                  if mention["name"] == subject), []),
            } for chapter in normalized],
        })
    alerts = []
    for echo in report["cross_chapter_echoes"]:
        alerts.append({
            "id": "echo:" + echo["phrase"],
            "kind": "repetition", "label": "Recurring phrase across chapters",
            "detail": f"“{echo['phrase']}” appears in {echo['chapters']} different chapters.",
            "references": echo["references"], "confidence": "literal",
        })
    for promise in report["promises"]:
        if promise["status"] == "open":
            alerts.append({
                "id": "promise:" + promise["id"],
                "kind": "plot", "label": "Author-tracked promise remains open",
                "detail": promise["title"] + f" · mentioned in {promise['reference_count']} chapter(s).",
                "references": [ref["path"] for ref in promise["references"]],
                "confidence": "author",
            })
    return {
        "chapters": normalized, "total_words": report["total_words"],
        "chapter_count": report["chapter_count"],
        "average_chapter_words": report["average_chapter_words"],
        "subject_presence": presence, "alerts": alerts[:100],
        "promises": report["promises"], "echoes": report["cross_chapter_echoes"],
        "limitations": "Descriptive and literal signals. Short chapters are not inherently bad; "
                       "name mentions do not prove agency, and a mechanical flag is not a literary verdict.",
        "local_only": True,
    }


def document_report(slug: str, path: str) -> dict:
    if not _is_editable(slug, path):
        raise ValueError("Select a tracked, editable manuscript chapter")
    source = read_text(slug, path)
    if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("Document exceeds the 1.5 MB revision safety limit")
    paragraphs = []
    for match in PARAGRAPH.finditer(source):
        snippet = match.group()
        if not snippet.strip():
            continue
        words = WORD.findall(snippet)
        paragraphs.append({
            "id": f"p{len(paragraphs)+1}", "start": match.start(), "end": match.end(),
            "text": snippet, "words": len(words),
            "dialogue": len(DIALOGUE.findall(snippet)),
            "transition_cues": len(BEAT_PATTERN.findall(snippet)),
            "line": source.count("\n", 0, match.start()) + 1,
        })
    return {
        "path": path, "content": source, "source_hash": _sha(source),
        "paragraphs": paragraphs, "words": len(WORD.findall(source)),
        "dialogue_passages": sum(p["dialogue"] for p in paragraphs),
        "revision_history": revisions.list_revisions(slug, path, limit=15),
        "limitations": "Paragraph metrics are observational, not prose quality assessments.",
    }


def apply_paragraph_changes(slug: str, path: str, source_hash: str, edits: list[dict]) -> dict:
    if not _is_editable(slug, path):
        raise ValueError("Only editable project manuscript chapters may be revised")
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise ValueError("Invalid source fingerprint")
    if not edits or len(edits) > 100:
        raise ValueError("Choose 1 to 100 paragraph edits")
    with _LOCK:
        original = document_report(slug, path)
        if original["source_hash"] != source_hash:
            raise ValueError("The chapter has changed since review. Reload before applying edits.")
        positions = {paragraph["id"]: paragraph for paragraph in original["paragraphs"]}
        seen = set()
        replacements = []
        for edit in edits:
            pid, replacement = edit.get("id"), edit.get("replacement")
            if pid not in positions or pid in seen:
                raise ValueError("An edit refers to an unknown or duplicate paragraph")
            if not isinstance(replacement, str) or len(replacement) > 20_000:
                raise ValueError("Edited paragraphs must contain at most 20,000 characters")
            if not replacement.strip():
                raise ValueError("Cannot silently erase a paragraph")
            if "\x00" in replacement:
                raise ValueError("Invalid paragraph content")
            seen.add(pid)
            source = positions[pid]
            if source["text"] == replacement:
                raise ValueError("Selected edit does not change the chapter")
            replacements.append((source["start"], source["end"], replacement))
        new_text = original["content"]
        for start, end, replacement in sorted(replacements, reverse=True):
            new_text = new_text[:start] + replacement + new_text[end:]
        if len(new_text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("Revised document exceeds size limit")
        prior = revisions.record_revision(
            slug, path, original["content"], source="before-manual-edit",
            note="Original preserved before Part 3 paragraph edits",
        )
        saved = save_text(slug, path, new_text)
        latest = revisions.record_revision(
            slug, path, new_text, source="author-approved-paragraph-edits",
            note=f"Accepted {len(edits)} targeted paragraph change(s)",
        )
        return {
            "path": path, "original_hash": source_hash, "new_hash": _sha(new_text),
            "edited_paragraphs": len(edits), "snapshot_id": saved["snapshot_id"],
            "before_revision": prior["id"], "after_revision": latest["id"],
            "diff": "".join(difflib.unified_diff(
                original["content"].splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile="original", tofile="accepted", n=2,
            ))[:80_000],
        }


SPEECH_VERBS = r"(?:said|asked|replied|whispered|shouted|murmured|answered|called|snapped|sighed)"
SPEAKER_AFTER = re.compile(
    rf"^\s*[,;]?\s*(?:{SPEECH_VERBS}\s+(?P<verb_first>[A-Z][a-zA-Z'-]+)|"
    rf"(?P<name_first>[A-Z][a-zA-Z'-]+)\s+{SPEECH_VERBS})\b"
)
SPEAKER_BEFORE = re.compile(
    rf"\b(?P<speaker>[A-Z][a-zA-Z'-]+)\s+{SPEECH_VERBS}\s*,?\s*$"
)
DIALOGUE_STOP = {"the", "and", "but", "that", "this", "with", "for", "you", "your",
                 "was", "were", "are", "they", "have", "not", "she", "him", "her",
                 "our", "from", "into", "what", "when", "where", "why", "who"}


def dialogue_report(slug: str, path: str) -> dict:
    """Quote-level *explicit* speaker attribution; no inferred dialogue ownership."""
    document = document_report(slug, path)
    source = document["content"]
    utterances = []
    groups = {}
    for match in DIALOGUE.finditer(source):
        words = WORD.findall(match.group())
        if not words:
            continue
        before = source[max(0, match.start() - 100):match.start()].split("\n")[-1]
        after = source[match.end():match.end() + 100].split("\n")[0]
        following = SPEAKER_AFTER.search(after)
        preceding = SPEAKER_BEFORE.search(before)
        speaker = (
            following.group("verb_first") or following.group("name_first")
            if following else preceding.group("speaker") if preceding else None
        )
        speaker = speaker or "Unattributed"
        utterance = {
            "id": f"q{len(utterances)+1}", "speaker": speaker,
            "attribution": "explicit_speech_tag" if speaker != "Unattributed" else "unattributed",
            "text": match.group(), "line": source.count("\n", 0, match.start()) + 1,
            "start": match.start(), "end": match.end(),
            "words": len(words),
        }
        utterances.append(utterance)
        if speaker not in groups:
            groups[speaker] = []
        groups[speaker].append(utterance)
        if len(utterances) >= 1200:
            break
    profiles = []
    for name, quotes in sorted(groups.items(), key=lambda row: (-len(row[1]), row[0])):
        from collections import Counter

        common = Counter(
            word.lower() for quote in quotes for word in WORD.findall(quote["text"])
            if len(word) >= 4 and word.lower() not in DIALOGUE_STOP
        )
        profiles.append({
            "name": name, "quote_count": len(quotes),
            "total_words": sum(q["words"] for q in quotes),
            "mean_quote_words": round(sum(q["words"] for q in quotes)/len(quotes), 1),
            "lexical_signatures": [
                {"word": word, "frequency": count} for word, count in common.most_common(6)
            ],
            "quotes": quotes[:24],
            "caveat": "Explicit attribution only" if name != "Unattributed" else
                      "Speaker not explicitly attributable from a nearby speech tag",
        })
    return {
        "path": path, "source_hash": document["source_hash"],
        "quote_count": len(utterances),
        "attributed_count": sum(u["attribution"] == "explicit_speech_tag" for u in utterances),
        "unattributed_count": sum(u["attribution"] == "unattributed" for u in utterances),
        "profiles": profiles,
        "timeline": utterances[:120],
        "limitations": "Mechanical quotation detection and immediate speech-tag matching only. "
                       "Narrative irony, subtext, speaker intention and untagged speech are not inferred. "
                       "Frequent words and quote length do not establish a distinct or authentic voice.",
    }


def restore_document_version(slug: str, path: str, expected_hash: str,
                             revision_id: str) -> dict:
    """Explicit author rollback with a current-source fingerprint guard.

    Uses the existing revision history implementation, which snapshots the
    overwritten chapter and records the restore as a new revision.
    """
    if not _is_editable(slug, path):
        raise ValueError("Only tracked manuscript files may be restored")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        raise ValueError("Invalid expected manuscript fingerprint")
    if not re.fullmatch(r"[a-f0-9]{32}", revision_id):
        raise ValueError("Invalid saved revision identifier")
    with _LOCK:
        current = document_report(slug, path)
        if current["source_hash"] != expected_hash:
            raise ValueError("The chapter has changed since review. Reload before restoring.")
        earlier = revisions.get_revision(slug, revision_id)
        if earlier["path"] != path:
            raise ValueError("Cannot restore a version from another chapter")
        if earlier["content_hash"] == current["source_hash"]:
            raise ValueError("This version already matches the current chapter")
        outcome = revisions.restore_revision(
            slug, revision_id, note="Author-approved restore from Part 3 revision workbench",
        )
        return {
            "path": path, "restored_from": revision_id,
            "previous_hash": current["source_hash"],
            "current_hash": _sha(read_text(slug, path)),
            "revision": outcome["revision"],
        }
