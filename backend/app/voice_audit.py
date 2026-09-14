from __future__ import annotations

from typing import Any

from .provenance_scan import WORD_RE, draft_documents
from .storage import read_text
from .style_fidelity import get_style_fidelity, measure_style
from .voice_audit_metrics import cadence_streaks, phrase_hits, symmetry_hits, voice_alignment


def analyze_voice(slug: str, path: str | None = None) -> dict[str, Any]:
    if path:
        text = read_text(slug, path)
        scope = path
    else:
        chunks = []
        for item in draft_documents(slug):
            try:
                chunks.append(read_text(slug, item["path"]))
            except (FileNotFoundError, OSError, ValueError):
                continue
        text = "\n\n".join(chunks)
        scope = "Draft"
    if not text.strip():
        raise ValueError("No prose is available for analysis")

    words = max(1, len(WORD_RE.findall(text)))
    metrics = {key: float(value) for key, value in measure_style(text).__dict__.items()}
    fidelity = get_style_fidelity(slug) or {}
    baseline = fidelity.get("metrics") if isinstance(fidelity.get("metrics"), dict) else {}
    alignment = voice_alignment(metrics, baseline)
    findings: list[dict[str, Any]] = []

    phrases = phrase_hits(text)
    if len(phrases) >= 2:
        findings.append({
            "id": "generic_scaffolding", "label": "Generic explanatory scaffolding",
            "count": len(phrases), "examples": phrases[:6],
            "suggestion": "Prefer concrete perception, behavior, subtext, or a precise thought native to the viewpoint character.",
        })

    symmetry = symmetry_hits(text)
    if len(symmetry) >= 2:
        findings.append({
            "id": "symmetry", "label": "Repeated symmetrical contrast",
            "count": len(symmetry), "examples": [{"excerpt": item} for item in symmetry],
            "suggestion": "Break some paired contrasts. Let one side remain implicit or express the turn through action or dialogue.",
        })

    streaks = cadence_streaks(text)
    if streaks:
        findings.append({
            "id": "cadence_uniformity", "label": "Uniform sentence cadence",
            "count": len(streaks), "examples": streaks,
            "suggestion": "Restore the learned author's natural sentence-length variation instead of smoothing every line into the same band.",
        })

    if alignment and alignment["deltas"]:
        findings.append({
            "id": "voice_drift", "label": "Drift from learned author fingerprint",
            "count": len(alignment["deltas"]), "examples": alignment["deltas"],
            "suggestion": "Use the fingerprint as a compass, not a quota; revise only mismatches that also feel unlike the author's real voice.",
        })

    return {
        "scope": scope, "words": words, "metrics": metrics, "baseline": baseline,
        "voice_alignment": alignment, "findings": findings,
        "author_rules": {
            "human_irregularities": fidelity.get("human_irregularities", []),
            "dialogue_rules": fidelity.get("dialogue_rules", []),
            "interiority_rules": fidelity.get("interiority_rules", []),
        },
        "disclaimer": "This audit measures craft patterns and similarity to the project's learned voice. It does not determine authorship.",
    }
