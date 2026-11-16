"""Multi-source checkpoint durability, pause/resume and series isolation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_extraction_batches as batches
from app import series_extraction_jobs as jobs
from app import series_model_readiness as readiness
from app import series_suggestions as suggestions
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    monkeypatch.setattr(readiness, "model_readiness", lambda _:
                        {"status": "available", "models": ["fictional:1b"]})
    sid = vault.create_series("Synthetic Multi-Book Batch")["id"]
    source_ids = []
    for book in (1, 2):
        value = "Ada was there before the bell rang in the courtyard. " + ("Then Bex crossed the bridge. " * 6)
        detail = vault.import_volume(
            sid, f"book-{book}.md", value.encode(), book, title=f"Book {book}",
            kind="novel", edition_status="reference", rights_confirmed=True,
        )
        source_ids.append(detail["volumes"][-1]["sources"][0]["id"])
    canon.add_entity(sid, "Ada", "character")
    calls = []

    async def fake_suggestions(series_id, source_id, start, stop, model):
        calls.append((source_id, start, stop, model))
        return {"suggestions": [], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", fake_suggestions)
    return sid, source_ids, calls


@pytest.mark.asyncio
async def test_two_books_advance_exactly_once_and_survive_reopen(sample):
    sid, sources, calls = sample
    prepared = batches.create(sid, "fictional:1b", 1, 2)
    assert prepared["status"] == "ready"
    assert prepared["source_count"] == 2
    assert prepared["auto_canon_approved"] is False
    assert batches.get(sid, prepared["id"])["processed_windows"] == 0
    first = await batches.advance(sid, prepared["id"])
    assert first["status"] == "ready"
    assert first["current_source_index"] == 1
    assert len(calls) == 1 and calls[0][0] == sources[0]
    checkpoint = batches.get(sid, prepared["id"])
    assert checkpoint["processed_windows"] == 1

    second = await batches.advance(sid, prepared["id"])
    assert second["status"] == "complete"
    assert second["current_source_index"] == 2
    assert len(calls) == 2 and calls[1][0] == sources[1]
    assert (await batches.advance(sid, prepared["id"]))["status"] == "complete"
    assert len(calls) == 2
    assert all(call[1] == 0 for call in calls)
    assert batches.get(sid, prepared["id"])["auto_canon_approved"] is False
    assert all(jobs.list_jobs(sid, source)[0]["candidate_count"] == 0 for source in sources)


@pytest.mark.asyncio
async def test_pause_resume_cancel_fail_closed(sample):
    sid, sources, calls = sample
    prepared = batches.create(sid, "fictional:1b", 1, 2)
    assert batches.pause(sid, prepared["id"])["status"] == "paused"
    with pytest.raises(ValueError, match="paused"):
        await batches.advance(sid, prepared["id"])
    assert batches.resume(sid, prepared["id"])["status"] == "ready"
    await batches.advance(sid, prepared["id"])
    paused = batches.pause(sid, prepared["id"])
    assert paused["current_source_index"] == 1
    assert batches.cancel(sid, prepared["id"])["status"] == "cancelled"
    with pytest.raises(ValueError, match="paused"):
        await batches.advance(sid, prepared["id"])
    assert len(calls) == 1
    assert sources[1] not in [call[0] for call in calls]


def test_batch_api_validation_and_cross_series_isolation(sample):
    sid, _, _ = sample
    foreign = vault.create_series("A Different Series")["id"]
    with TestClient(app) as client:
        created = client.post(f"/api/series/{sid}/extraction-batches",
                              json={"model": "fictional:1b", "book_from": 1, "book_to": 2})
        assert created.status_code == 201, created.text
        batch = created.json()
        assert batch["source_count"] == 2
        assert client.get(f"/api/series/{sid}/extraction-batches").json()[0]["id"] == batch["id"]
        assert client.get(f"/api/series/{foreign}/extraction-batches/{batch['id']}").status_code == 404
        assert client.post(f"/api/series/{foreign}/extraction-batches/{batch['id']}/pause").status_code == 404
        assert client.post(f"/api/series/{sid}/extraction-batches",
                           json={"model": "not-installed", "book_from": 1, "book_to": 2}).status_code == 400
        assert client.post(f"/api/series/{sid}/extraction-batches",
                           json={"model": "fictional:1b", "book_from": 2, "book_to": 1}).status_code == 400


@pytest.mark.asyncio
async def test_pause_during_running_window_commits_once_then_stops(sample, monkeypatch):
    import asyncio

    sid, sources, calls = sample
    entering = asyncio.Event()
    release = asyncio.Event()

    async def delayed(series_id, source_id, start, stop, model):
        calls.append((source_id, start, stop, model))
        entering.set()
        await release.wait()
        return {"suggestions": [], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", delayed)
    batch = batches.create(sid, "fictional:1b", 1, 2)
    task = asyncio.create_task(batches.advance(sid, batch["id"]))
    await asyncio.wait_for(entering.wait(), timeout=5)
    requested = batches.pause(sid, batch["id"])
    assert requested["status"] == "pause_requested"
    release.set()
    checkpoint = await asyncio.wait_for(task, timeout=5)
    assert checkpoint["status"] == "paused"
    assert checkpoint["current_source_index"] == 1
    assert len(calls) == 1
    with pytest.raises(ValueError, match="paused"):
        await batches.advance(sid, batch["id"])
    assert batches.resume(sid, batch["id"])["status"] == "ready"
    finished = await batches.advance(sid, batch["id"])
    assert finished["status"] == "complete"
    assert [call[0] for call in calls] == sources


@pytest.mark.asyncio
async def test_cancelled_inflight_window_releases_both_leases(sample, monkeypatch):
    import asyncio

    sid, sources, _ = sample
    entered = asyncio.Event()
    started = asyncio.Event()

    async def suspended(*args):
        entered.set()
        try:
            await asyncio.sleep(40)
        finally:
            started.set()

    monkeypatch.setattr(suggestions, "suggest_facts", suspended)
    batch = batches.create(sid, "fictional:1b", 1, 2)
    task = asyncio.create_task(batches.advance(sid, batch["id"]))
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert started.is_set()
    paused = batches.get(sid, batch["id"])
    assert paused["status"] == "paused"
    source_job = jobs.list_jobs(sid, sources[0])[0]
    assert source_job["status"] == "error"
    assert source_job["next_offset"] == 0
    assert source_job["candidate_count"] == 0
    assert batches.resume(sid, batch["id"])["status"] == "ready"
