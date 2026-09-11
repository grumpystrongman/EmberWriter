from pathlib import Path

import pytest

from app import editorial, editorial_fix, revisions, storage
from app.editorial_models import EditorialFixApplyRequest, EditorialFixRequest, EditorialRunRequest
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


@pytest.mark.asyncio
async def test_editorial_fix_targets_sentence_and_preserves_source(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Fix")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    source = "# Chapter 1\n\nMara walked quietly across the empty room. The lantern shook in her hand.\n"
    storage.save_text(slug, path, source)
    run = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="document", path=path, reports=["adverb"]),
    )
    finding = next(item for item in run["items"] if item["report_id"] == "adverb")
    captured: dict = {}

    async def fake_generate(config, messages, temperature=0.9, top_p=0.95, json_mode=False):
        captured["messages"] = messages
        captured["temperature"] = temperature
        captured["json_mode"] = json_mode
        return '{"replacement":"Mara crept across the empty room.","rationale":"A stronger verb carries the quiet movement without the adverb."}'

    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    proposal = await editorial_fix.propose_editorial_fix(
        slug,
        EditorialFixRequest(
            finding_id=finding["id"],
            provider=ProviderConfig(model="test-model"),
        ),
    )

    assert proposal.path == path
    assert proposal.original == "Mara walked quietly across the empty room."
    assert proposal.replacement == "Mara crept across the empty room."
    assert proposal.changed is True
    assert proposal.target_end > proposal.target_start
    assert captured["json_mode"] is True
    assert captured["temperature"] == 0.35
    assert "Flagged anchor: quietly" in captured["messages"][1]["content"]
    assert storage.read_text(slug, path) == source


@pytest.mark.asyncio
async def test_editorial_fix_apply_updates_manuscript_revision_and_finding(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Fix Apply")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    source = "# Chapter 1\n\nMara walked quietly across the empty room. The lantern shook.\n"
    storage.save_text(slug, path, source)
    revisions.record_revision(slug, path, source, source="save")
    run = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="document", path=path, reports=["adverb"]),
    )
    finding = next(item for item in run["items"] if item["report_id"] == "adverb")

    async def fake_generate(config, messages, temperature=0.9, top_p=0.95, json_mode=False):
        return '{"replacement":"Mara crept across the empty room.","rationale":"Use the verb to carry the movement."}'

    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    proposal = await editorial_fix.propose_editorial_fix(
        slug,
        EditorialFixRequest(finding_id=finding["id"], provider=ProviderConfig(model="test-model")),
    )
    applied = editorial_fix.apply_editorial_fix(
        slug,
        EditorialFixApplyRequest(
            finding_id=proposal.finding_id,
            path=proposal.path,
            original=proposal.original,
            replacement=proposal.replacement,
            source_hash=proposal.source_hash,
            target_start=proposal.target_start,
            target_end=proposal.target_end,
            rationale=proposal.rationale,
        ),
    )

    updated = storage.read_text(slug, path)
    assert "Mara crept across the empty room." in updated
    assert "walked quietly" not in updated
    assert applied.finding.status == "resolved"
    assert applied.content == updated
    history = revisions.list_revisions(slug, path)
    assert history[0]["source"] == "editorial_fix"
    assert history[0]["note"].startswith("Adverbs AI fix")
    refreshed = editorial.get_editorial_run(slug, run["id"])
    resolved = next(item for item in refreshed["items"] if item["id"] == finding["id"])
    assert resolved["status"] == "resolved"
    assert resolved["stale"] is True


@pytest.mark.asyncio
async def test_editorial_fix_apply_rejects_stale_proposal_without_changes(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Apply Stale")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    source = "# Chapter 1\n\nMara walked quietly across the room.\n"
    storage.save_text(slug, path, source)
    run = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="document", path=path, reports=["adverb"]),
    )
    finding = next(item for item in run["items"] if item["report_id"] == "adverb")

    async def fake_generate(config, messages, temperature=0.9, top_p=0.95, json_mode=False):
        return '{"replacement":"Mara crept across the room.","rationale":"Stronger verb."}'

    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    proposal = await editorial_fix.propose_editorial_fix(
        slug,
        EditorialFixRequest(finding_id=finding["id"], provider=ProviderConfig(model="test-model")),
    )
    newer = "# Chapter 1\n\nMara crossed the room carrying a lamp.\n"
    storage.save_text(slug, path, newer)

    with pytest.raises(ValueError, match="stale"):
        editorial_fix.apply_editorial_fix(
            slug,
            EditorialFixApplyRequest(
                finding_id=proposal.finding_id,
                path=proposal.path,
                original=proposal.original,
                replacement=proposal.replacement,
                source_hash=proposal.source_hash,
                target_start=proposal.target_start,
                target_end=proposal.target_end,
                rationale=proposal.rationale,
            ),
        )
    assert storage.read_text(slug, path) == newer
    remaining = next(item for item in editorial.get_editorial_run(slug, run["id"])["items"] if item["id"] == finding["id"])
    assert remaining["status"] == "open"


@pytest.mark.asyncio
async def test_editorial_fix_rejects_stale_finding_before_model_call(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Editorial Fix Stale")
    slug = project["slug"]
    path = "manuscript/chapter-001.md"
    storage.save_text(slug, path, "# Chapter 1\n\nMara walked quietly across the room.\n")
    run = editorial.run_editorial(
        slug,
        EditorialRunRequest(scope="document", path=path, reports=["adverb"]),
    )
    finding = next(item for item in run["items"] if item["report_id"] == "adverb")
    storage.save_text(slug, path, "# Chapter 1\n\nMara crossed the room.\n")
    called = False

    async def fake_generate(*args, **kwargs):
        nonlocal called
        called = True
        return '{}'

    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    with pytest.raises(ValueError, match="stale"):
        await editorial_fix.propose_editorial_fix(
            slug,
            EditorialFixRequest(
                finding_id=finding["id"],
                provider=ProviderConfig(model="test-model"),
            ),
        )
    assert called is False
