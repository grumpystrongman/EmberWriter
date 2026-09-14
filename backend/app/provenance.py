from __future__ import annotations

from collections import defaultdict
from typing import Any

from .provenance_scan import artifact_counts, document_fingerprints
from .provenance_score import evidence_strength, later_revision_count
from .provenance_store import assistance_decisions, assistance_events, revision_rows
from .storage import utc_now


def provenance_summary(slug: str) -> dict[str, Any]:
    revisions = revision_rows(slug)
    events = assistance_events(slug)
    decisions = assistance_decisions(slug)
    artifacts = artifact_counts(slug)
    documents, words, project_hash, by_path = document_fingerprints(slug)
    later = later_revision_count(events, by_path)

    sources: dict[str, int] = defaultdict(int)
    for row in revisions:
        sources[str(row["source"])] += 1

    decision_counts: dict[str, int] = defaultdict(int)
    for row in decisions:
        decision_counts[str(row["decision"])] += 1
    reviewed_event_ids = {str(row["assistance_event_id"]) for row in decisions}

    return {
        "generated_at": utc_now(),
        "project": slug,
        "draft": {
            "documents": len(documents),
            "words": words,
            "project_hash": project_hash,
        },
        "provenance": {
            "total_revisions": len(revisions),
            "revision_sources": dict(sorted(sources.items())),
            "assistance_events": len(events),
            "assistance_decisions": len(decisions),
            "assistance_decision_counts": dict(sorted(decision_counts.items())),
            "unreviewed_assistance_events": max(0, len(events) - len(reviewed_event_ids)),
            "assistance_events_with_later_revisions": later,
            "first_evidence_at": min((row["created_at"] for row in revisions), default=None),
            "last_evidence_at": max((row["created_at"] for row in revisions), default=None),
            "artifacts": artifacts,
        },
        "evidence_strength": evidence_strength(len(documents), revisions, events, artifacts, later),
        "documents": documents,
        "recent_assistance_events": events[-20:][::-1],
        "recent_assistance_decisions": decisions[-20:][::-1],
        "cautions": [
            "This is provenance evidence, not a mathematical proof of authorship.",
            "Local timestamps and hashes establish internal consistency but are not independent third-party notarization.",
            "Generation alone does not imply acceptance. Accepted, rejected, partial, or copied suggestions are recorded only when the author uses the corresponding review control.",
        ],
    }
