from __future__ import annotations

import json
import re

from .provenance import provenance_summary
from .provenance_store import assistance_decisions, assistance_events, revision_rows, text_hash
from .storage import save_text, utc_now


def export_provenance(slug: str) -> dict[str, str]:
    summary = provenance_summary(slug)
    manifest = {
        "schema_version": 2,
        "kind": "emberwriter-writing-provenance",
        "generated_at": utc_now(),
        "summary": summary,
        "revision_lineage": revision_rows(slug),
        "assistance_events": assistance_events(slug),
        "assistance_decisions": assistance_decisions(slug),
    }
    canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = text_hash(canonical)
    manifest["manifest_sha256"] = digest
    stamp = re.sub(r"[^0-9]", "", manifest["generated_at"])[:14]
    json_path = f"exports/provenance/writing-provenance-{stamp}.json"
    md_path = f"exports/provenance/writing-provenance-{stamp}.md"
    save_text(slug, json_path, json.dumps(manifest, indent=2, ensure_ascii=False))

    record = summary["provenance"]
    strength = summary["evidence_strength"]
    counts = record.get("assistance_decision_counts", {})
    accepted = int(counts.get("accepted_append", 0)) + int(counts.get("accepted_replace", 0))
    lines = [
        "# EmberWriter Writing Provenance Report", "",
        f"Generated: {manifest['generated_at']}",
        f"Project: {slug}",
        f"Manifest SHA-256: `{digest}`", "",
        "## Current manuscript",
        f"- Draft documents: {summary['draft']['documents']}",
        f"- Draft words: {summary['draft']['words']}",
        f"- Project fingerprint: `{summary['draft']['project_hash']}`", "",
        "## Creation record",
        f"- Recoverable revisions: {record['total_revisions']}",
        f"- Writing assistance events: {record['assistance_events']}",
        f"- Assistance suggestions explicitly reviewed: {record.get('assistance_decisions', 0)}",
        f"- Suggestions accepted into the editor: {accepted}",
        f"- Suggestions rejected: {int(counts.get('rejected', 0))}",
        f"- Suggestions partially used: {int(counts.get('partial', 0))}",
        f"- Suggestions copied for separate use: {int(counts.get('copied', 0))}",
        f"- Suggestions without a recorded review decision: {record.get('unreviewed_assistance_events', 0)}",
        f"- Assistance events followed by later revisions: {record['assistance_events_with_later_revisions']}",
        f"- First recorded revision: {record['first_evidence_at'] or 'n/a'}",
        f"- Latest recorded revision: {record['last_evidence_at'] or 'n/a'}", "",
        "## Evidence strength",
        f"Internal evidence rating: **{strength['label']} ({strength['score']}/100)**", "",
        *[f"- {reason}" for reason in strength["reasons"]], "",
        "## Important limits",
        *[f"- {item}" for item in summary["cautions"]], "",
        "This report documents a creative and revision process. It is not a legal opinion or third-party timestamp attestation.",
    ]
    save_text(slug, md_path, "\n".join(lines) + "\n")
    return {
        "json_path": json_path,
        "markdown_path": md_path,
        "manifest_sha256": digest,
        "generated_at": manifest["generated_at"],
    }
