from pathlib import Path

from app import storage
from app.provenance_score import evidence_strength, later_revision_count
from app.provenance_store import assistance_events, record_assistance_event
from app.voice_audit_metrics import cadence_streaks, phrase_hits, symmetry_hits, voice_alignment


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_assistance_event_stores_hashes_and_metadata(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Provenance Test")
    slug = project["slug"]

    result = record_assistance_event(
        slug,
        mode="rewrite",
        active_file="manuscript/chapter-01.md",
        prompt="Make the confrontation tenser.",
        selected_text="Original scene text.",
        output_text="Revised scene text with more pressure.",
        context_files=["characters/mara.md", "style/voice-profile.json"],
        refined=True,
        provider="ollama",
        model="test-model",
    )

    rows = assistance_events(slug)
    assert len(rows) == 1
    assert rows[0]["id"] == result["id"]
    assert rows[0]["mode"] == "rewrite"
    assert rows[0]["active_file"] == "manuscript/chapter-01.md"
    assert rows[0]["output_words"] == 6
    assert rows[0]["refined"] is True
    assert len(rows[0]["prompt_hash"]) == 64
    assert len(rows[0]["output_hash"]) == 64
    assert "prompt" not in rows[0]
    assert "output_text" not in rows[0]


def test_evidence_strength_rewards_lineage_without_claiming_proof() -> None:
    revisions = [
        {"created_at": "2026-01-01T12:00:00+00:00"},
        {"created_at": "2026-02-15T12:00:00+00:00"},
    ]
    events = [{"created_at": "2026-01-15T12:00:00+00:00", "active_file": "manuscript/a.md"}]
    by_path = {
        "manuscript/a.md": [
            {"created_at": "2026-02-01T12:00:00+00:00"},
        ]
    }
    later = later_revision_count(events, by_path)
    result = evidence_strength(
        4,
        revisions,
        events,
        {"voice_profile": True, "style_fidelity": True, "characters": 4, "world": 5, "relationships": 3},
        later,
    )
    assert later == 1
    assert result["score"] >= 60
    assert result["label"] in {"moderate", "strong"}
    assert any("revision" in reason.lower() for reason in result["reasons"])


def test_voice_metrics_find_uniformity_and_drift() -> None:
    text = (
        "In that moment, Mara knew the door was closed. "
        "For a moment, Mara kept her hands still. "
        "It was not fear but caution that held her. "
        "It was not anger but focus that moved her. "
        "Mara crossed the room without looking back. "
        "Mara reached the window and stopped there."
    )
    assert len(phrase_hits(text)) >= 2
    assert len(symmetry_hits(text)) >= 2
    assert cadence_streaks("One two three four five. Six seven eight nine ten. Red blue green black white. Rain wind stone smoke flame.")

    alignment = voice_alignment(
        {
            "avg_sentence_words": 26.0,
            "sentence_stddev": 1.0,
            "short_sentence_ratio": 0.0,
            "long_sentence_ratio": 0.7,
            "avg_paragraph_words": 180.0,
            "dialogue_ratio": 0.0,
            "fragment_ratio": 0.0,
            "em_dash_rate": 0.0,
        },
        {
            "avg_sentence_words": 11.0,
            "sentence_stddev": 7.0,
            "short_sentence_ratio": 0.35,
            "long_sentence_ratio": 0.1,
            "avg_paragraph_words": 65.0,
            "dialogue_ratio": 0.3,
            "fragment_ratio": 0.18,
            "em_dash_rate": 2.0,
        },
    )
    assert alignment is not None
    assert alignment["score"] < 82
    assert alignment["deltas"]
