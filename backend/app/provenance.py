from __future__ import annotations

from collections import defaultdict
from typing import Any

from .provenance_scan import artifact_counts, document_fingerprints
from .provenance_score import evidence_strength, later_revision_count
from .provenance_store import assistance_events, revision_rows
from .storage import utc_now


def provenance_summary(slug: str) -> dict[str, Any]:
    revisions = revision_rows(slug)
    events = assistance_events(slug)
    artifacts = artifact_counts(slug)
    documents, words, project_hash, by_path = document_fingerprints(slug)
    later = later_revision_count(events, by_path)

    sources: dict[str, int] = defaultdict(int)
    for row in revisions:
        sources[str(row["source"])] += 1

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
            "assistance_events_with_later_revisions": later,
            "first_evidence_at": min((row["created_at"] for row in revisions), default=None),
            "last_evidence_at": max((row["created_at"] for row in revisions), default=None),
            "artifacts": artifacts,
        },
        "evidence_strength": evidence_strength(len(documents), revisions, events, artifacts, later),
        "documents": documents,
        "recent_assistance_events": events[-20:][::-1],
        "cautions": [
            "This is provenance evidence, not a mathematical proof of authorship.",
            "Local timestamps and hashes establish internal consistency but are not independent third-party notarization.",
            "An assistance event records that a suggestion was generated; it does not claim the suggestion was accepted into the manuscript.",
        ],
    }
