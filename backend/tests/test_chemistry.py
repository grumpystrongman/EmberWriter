import asyncio
import json
from pathlib import Path

from app import chemistry, storage
from app.models import (
    AftermathAnalyzeRequest,
    AftermathProposal,
    AftermathRelationshipUpdate,
    ChemistryInferRequest,
    ChemistryMilestone,
    ProviderConfig,
    RelationshipChemistryProfile,
)


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_chemistry_profile_round_trip_and_context(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Chemistry Test")
    slug = project["slug"]
    profile = RelationshipChemistryProfile(
        participants=["Mira", "Rowan"],
        dynamic_summary="Precision meeting patient attention.",
        verbal_rhythm="Mira is deliberate; Rowan listens before answering.",
        boundaries=["Mira must choose any surrender explicitly."],
        next_escalations=["Mira voluntarily asks for help instead of commanding it."],
    )

    saved, path = chemistry.save_chemistry_profile(slug, profile)
    loaded = chemistry.get_chemistry_profile(slug, ["Rowan", "Mira"])
    context, files = chemistry.build_chemistry_context(slug, ["Mira", "Rowan"])

    assert saved.updated_at
    assert path == "relationships/chemistry/rowan--mira.json"
    assert loaded is not None
    assert loaded.boundaries == ["Mira must choose any surrender explicitly."]
    assert "Precision meeting patient attention" in context
    assert "Author-controlled boundaries" in context
    assert path in files


def test_apply_aftermath_preserves_author_boundaries(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Aftermath Apply Test")
    slug = project["slug"]
    chemistry.save_chemistry_profile(
        slug,
        RelationshipChemistryProfile(
            participants=["Tamsin", "Rowan"],
            dynamic_summary="Fierce trust under construction.",
            boundaries=["Do not treat physical intensity as permission to override a verbal stop."],
            milestones=[
                ChemistryMilestone(
                    label="First trust",
                    consequence="Tamsin accepts comfort without leaving.",
                    source_path="manuscript/chapter-004.md",
                    chapter_order=4,
                )
            ],
        ),
    )
    proposal = AftermathProposal(
        summary="Tamsin allows herself to be held after danger.",
        participants=["Tamsin", "Rowan"],
        source_path="manuscript/chapter-007.md",
        chapter_order=7,
        relationship_updates=[
            AftermathRelationshipUpdate(
                participants=["Tamsin", "Rowan"],
                dynamic_summary="Intensity now includes a place of safety.",
                trust_state="Tamsin trusts Rowan to stay present when she stops fighting.",
                add_established_patterns=["Holding can calm rather than contain Tamsin."],
                next_escalations=["Tamsin asks for comfort before reaching overload."],
                milestone_label="Quiet inside the fire",
                milestone_consequence="Safety becomes compatible with strength.",
            )
        ],
    )

    profiles, paths = chemistry.apply_aftermath(slug, proposal)

    assert paths == ["relationships/chemistry/tamsin--rowan.json"]
    assert profiles[0].boundaries == [
        "Do not treat physical intensity as permission to override a verbal stop."
    ]
    assert profiles[0].milestones[-1].label == "Quiet inside the fire"
    assert profiles[0].milestones[-1].chapter_order == 7
    assert "Holding can calm" in profiles[0].established_patterns[0]


def test_infer_chemistry_uses_model_and_saves(tmp_path: Path, monkeypatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Infer Chemistry Test")
    slug = project["slug"]
    storage.save_text(slug, "characters/mira.md", "# Mira\n\nPrecise and guarded.")
    storage.save_text(slug, "characters/rowan.md", "# Rowan\n\nAttentive and empathic.")

    async def fake_generate(*args, **kwargs):
        return json.dumps(
            {
                "participants": ["Mira", "Rowan"],
                "dynamic_summary": "Control meeting attentive patience.",
                "attraction_language": "Measured challenge and close attention.",
                "verbal_rhythm": "Precise teasing answered with patient observation.",
                "initiation_style": "Mira tests; Rowan waits for the choice beneath the test.",
                "response_style": "Rowan reflects pressure without stealing agency.",
                "power_dynamic": "Control becomes meaningful only when voluntarily yielded.",
                "trust_state": "Developing.",
                "vulnerability_pressure": "Mira fears being diminished by surrender.",
                "established_patterns": [],
                "boundaries": [],
                "signature_elements": ["deliberate verbal choices"],
                "lore_resonance": ["Command changes quality when surrender is voluntary"],
                "aftermath_needs": ["name what changed without making Mira smaller"],
                "next_escalations": ["Mira explicitly chooses vulnerability"],
                "avoidances": ["generic dominance shorthand"],
                "milestones": [],
                "author_notes": "",
            }
        )

    monkeypatch.setattr(chemistry, "generate", fake_generate)
    result = asyncio.run(
        chemistry.infer_chemistry(
            slug,
            ChemistryInferRequest(
                participants=["Mira", "Rowan"],
                provider=ProviderConfig(model="test-model"),
                save=True,
            ),
        )
    )

    assert result["profile"].dynamic_summary.startswith("Control meeting")
    assert result["profile"].boundaries == []
    assert result["saved_path"] == "relationships/chemistry/rowan--mira.json"


def test_reinfer_preserves_author_owned_fields(tmp_path: Path, monkeypatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Protected Chemistry Test")
    slug = project["slug"]
    chemistry.save_chemistry_profile(
        slug,
        RelationshipChemistryProfile(
            participants=["Mira", "Rowan"],
            dynamic_summary="Old derived state.",
            boundaries=["Only explicit voluntary surrender counts as surrender."],
            author_notes="Do not turn Mira into a generic submissive archetype.",
            milestones=[
                ChemistryMilestone(
                    label="Chosen trust",
                    consequence="Mira asks rather than commands.",
                    source_path="manuscript/chapter-006.md",
                    chapter_order=6,
                )
            ],
        ),
    )

    async def fake_generate(*args, **kwargs):
        return json.dumps(
            {
                "participants": ["Mira", "Rowan"],
                "dynamic_summary": "Fresh model-derived state.",
                "attraction_language": "Attention and challenge.",
                "verbal_rhythm": "Measured.",
                "initiation_style": "Deliberate.",
                "response_style": "Attentive.",
                "power_dynamic": "Chosen shifts.",
                "trust_state": "Stronger.",
                "vulnerability_pressure": "Fear of losing self.",
                "established_patterns": [],
                "boundaries": ["MODEL SHOULD NOT REPLACE THIS"],
                "signature_elements": [],
                "lore_resonance": [],
                "aftermath_needs": [],
                "next_escalations": [],
                "avoidances": [],
                "milestones": [],
                "author_notes": "MODEL SHOULD NOT REPLACE THIS",
            }
        )

    monkeypatch.setattr(chemistry, "generate", fake_generate)
    result = asyncio.run(
        chemistry.infer_chemistry(
            slug,
            ChemistryInferRequest(
                participants=["Mira", "Rowan"],
                provider=ProviderConfig(model="test-model"),
                save=True,
            ),
        )
    )

    profile = result["profile"]
    assert profile.dynamic_summary == "Fresh model-derived state."
    assert profile.boundaries == ["Only explicit voluntary surrender counts as surrender."]
    assert profile.author_notes == "Do not turn Mira into a generic submissive archetype."
    assert profile.milestones[0].label == "Chosen trust"


def test_aftermath_analysis_sets_source_and_chapter(tmp_path: Path, monkeypatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Analyze Aftermath Test")
    slug = project["slug"]

    async def fake_generate(*args, **kwargs):
        return json.dumps(
            {
                "summary": "Trust changes after the scene.",
                "participants": ["Ari", "Bea"],
                "relationship_updates": [
                    {
                        "participants": ["Ari", "Bea"],
                        "dynamic_summary": "More open than before.",
                        "trust_state": "Higher trust.",
                        "vulnerability_pressure": "A truth remains unsaid.",
                        "add_established_patterns": ["They stay after difficult honesty."],
                        "add_signature_elements": [],
                        "add_lore_resonance": [],
                        "add_aftermath_needs": ["Talk about the unsaid truth."],
                        "next_escalations": ["Ask the question directly."],
                        "milestone_label": "Stayed",
                        "milestone_consequence": "Neither person fled after vulnerability.",
                    }
                ],
                "character_aftermath": ["Ari is unsettled but relieved."],
                "open_questions": ["Will Bea ask what Ari withheld?"],
            }
        )

    monkeypatch.setattr(chemistry, "generate", fake_generate)
    proposal = asyncio.run(
        chemistry.analyze_aftermath(
            slug,
            AftermathAnalyzeRequest(
                scene_text="A" * 300,
                provider=ProviderConfig(model="test-model"),
                source_path="manuscript/chapter-012.md",
                participants=["Ari", "Bea"],
            ),
        )
    )

    assert proposal.source_path == "manuscript/chapter-012.md"
    assert proposal.chapter_order == 12
    assert proposal.relationship_updates[0].milestone_label == "Stayed"
