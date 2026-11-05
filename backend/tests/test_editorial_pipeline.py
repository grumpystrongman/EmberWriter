"""Author-approved coordinated editorial revision tests using synthetic prose."""
import pytest
from fastapi.testclient import TestClient

from app import editorial, editorial_fix, editorial_pipeline, storage
from app.editorial_models import EditorialRunRequest
from app.main import app
from app.models import ProviderConfig


@pytest.mark.asyncio
async def test_bookwide_proposals_never_touch_source_without_author_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    slug = storage.create_project("Synthetic Whole Book Revision")["slug"]
    first, second = "manuscript/chapter-001.md", "manuscript/chapter-002.md"
    one = "# Opening\n\nMara walked quietly through the hall."
    two = "# Ending\n\nTomas smiled softly into the dawn."
    storage.save_text(slug, first, one)
    storage.save_text(slug, second, two)
    from app.binder import sync_binder
    sync_binder(slug)
    run = editorial.run_editorial(
        slug, EditorialRunRequest(scope="draft", reports=["adverb"]))
    plan = editorial_pipeline.plan(slug, run["id"], limit=20)
    assert len(plan["items"]) == 2
    assert {item["path"] for item in plan["items"]} == {first, second}
    assert not any(item["replacement"] for item in plan["items"])
    assert storage.read_text(slug, first) == one

    async def fake_generate(config, messages, temperature=.35, top_p=.9, json_mode=True):
        manuscript_prompt = messages[1]["content"]
        if "walked quietly" in manuscript_prompt:
            return '{"replacement":"Mara crept through the hall.","rationale":"Precise verb."}'
        return '{"replacement":"Tomas smiled at the dawn.","rationale":"Lean phrasing."}'
    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    staged = await editorial_pipeline.propose(slug, plan["id"], ProviderConfig(model="test-model"))
    assert staged["status"] == "proposed"
    assert all(item["replacement"] for item in staged["items"])
    assert storage.read_text(slug, first) == one
    assert storage.read_text(slug, second) == two
    approved = [item["finding_id"] for item in staged["items"]]
    with pytest.raises(ValueError, match="approval"):
        editorial_pipeline.apply(slug, plan["id"], approved, False)
    done = editorial_pipeline.apply(slug, plan["id"], approved, True)
    assert done["status"] == "applied"
    assert len(done["changed_paths"]) == 2
    assert "crept through" in storage.read_text(slug, first)
    assert "smiled at" in storage.read_text(slug, second)
    assert done["fresh_run_id"]
    assert TestClient(app).get(f"/api/projects/{slug}/editorial/batch").json()["status"] == "applied"


@pytest.mark.asyncio
async def test_edition_changes_invalidate_all_staged_book_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    slug = storage.create_project("Synthetic Concurrent Editorial")["slug"]
    path = "manuscript/chapter-001.md"
    source = "# Opening\n\nMara walked quietly through the hall."
    storage.save_text(slug, path, source)
    run = editorial.run_editorial(slug, EditorialRunRequest(
        scope="document", path=path, reports=["adverb"]))
    plan = editorial_pipeline.plan(slug, run["id"])
    async def fake_generate(*args, **kwargs):
        return '{"replacement":"Mara crept into the hall.","rationale":"Shortened."}'
    monkeypatch.setattr(editorial_fix, "generate", fake_generate)
    staged = await editorial_pipeline.propose(slug, plan["id"], ProviderConfig(model="test-model"))
    storage.save_text(slug, path, source + "\nThe light died.")
    with pytest.raises(ValueError, match="changed"):
        editorial_pipeline.apply(slug, plan["id"], [staged["items"][0]["finding_id"]], True)
    assert storage.read_text(slug, path).endswith("The light died.")
