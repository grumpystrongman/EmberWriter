"""Stage II chunk 2: bounded source extraction jobs (synthetic only)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_extraction_jobs as jobs
from app import series_suggestions as suggestions
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("A Synthetic Expedition")["id"]
    # Three windows without real book prose. Exact quote offsets matter.
    text = ("Mira trusts Rowan. " + "A small harmless invented sentence. " * 46
            + "Mira fears a bridge. " + "A second harmless invented sentence. " * 43
            + "Mira protects Rowan.")
    book = vault.import_volume(
        sid, "test.txt", text.encode("utf-8"), 1, title="A Fictional Book",
        kind="novel", edition_status="reference", rights_confirmed=True)
    source = book["volumes"][0]["sources"][0]
    mira = canon.add_entity(sid, "Mira", "character")
    rowan = canon.add_entity(sid, "Rowan", "character")
    return sid, source, text, mira, rowan


@pytest.mark.asyncio
async def test_resumable_progress_exact_quotes_and_no_auto_approval(sample, monkeypatch):
    sid, source, text, mira, _rowan = sample
    seen = []

    async def fake_suggest(series_id, source_id, start, end, model):
        assert series_id == sid and source_id == source["id"]
        assert end - start <= jobs.WINDOW_CHARS
        assert start == (seen[-1][1] if seen else 0)
        seen.append((start, end))
        excerpt = text[start:end]
        candidate = []
        phrase = "Mira trusts Rowan."
        pos = excerpt.find(phrase)
        if pos >= 0:
            candidate = [{
                "subject_id": mira["id"], "subject_name": "Mira",
                "predicate": "trusts", "object_text": "Rowan",
                "scope": "world", "knower_id": None,
                "quote_start": start + pos, "quote_end": start + pos + len(phrase),
                "quote": phrase, "source_id": source_id,
                "start_book": 1, "start_sequence": 0,
                "status": "suggestion_not_saved_or_approved",
            }]
        return {"suggestions": candidate, "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", fake_suggest)
    first = jobs.create(sid, source["id"], "local-test")
    again = jobs.create(sid, source["id"], "local-test")
    assert first["id"] == again["id"]  # idempotent resume
    assert first["progress_percent"] == 0
    assert not canon.list_facts(sid)

    state = first
    for i in range(10):
        state = await jobs.advance(sid, first["id"])
        assert state["processed_windows"] == i + 1
        assert state["next_offset"] == seen[-1][1]
        assert not canon.list_facts(sid)
        if state["status"] == "complete":
            break
    assert state["status"] == "complete"
    assert state["progress_percent"] == 100
    assert state["candidate_count"] == 1
    assert state["candidates"][0]["quote"] == "Mira trusts Rowan."
    assert text[state["candidates"][0]["quote_start"]:state["candidates"][0]["quote_end"]] == state["candidates"][0]["quote"]
    assert (await jobs.advance(sid, first["id"]))["processed_windows"] == len(seen)
    assert jobs.list_jobs(sid, source["id"])[0]["id"] == first["id"]
    assert jobs.get(sid, first["id"])["auto_canon_approved"] is False


@pytest.mark.asyncio
async def test_timeout_retry_does_not_skip_passages(sample, monkeypatch):
    sid, source, _, _, _ = sample
    attempts = []

    async def flaky(*args):
        attempts.append(args[2:4])
        if len(attempts) == 1:
            raise TimeoutError("source text should not be logged")
        return {"suggestions": [], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", flaky)
    job = jobs.create(sid, source["id"], "local-test")
    with pytest.raises(TimeoutError):
        await jobs.advance(sid, job["id"])
    failed = jobs.get(sid, job["id"])
    assert failed["status"] == "error"
    assert failed["next_offset"] == 0
    assert "source text" not in failed["error"]
    resumed = await jobs.advance(sid, job["id"])
    assert resumed["next_offset"] > 0
    assert attempts[0] == attempts[1]


@pytest.mark.asyncio
async def test_concurrent_run_is_blocked_and_cancellation_is_author_controlled(sample, monkeypatch):
    sid, source, _, _, _ = sample
    entered = asyncio.Event()
    release = asyncio.Event()

    async def delayed(*args):
        entered.set()
        await release.wait()
        return {"suggestions": [], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", delayed)
    job = jobs.create(sid, source["id"], "local-test")
    task = asyncio.create_task(jobs.advance(sid, job["id"]))
    await entered.wait()
    with pytest.raises(ValueError, match="already running"):
        await jobs.advance(sid, job["id"])
    with pytest.raises(ValueError, match="running"):
        jobs.cancel(sid, job["id"])
    release.set()
    await task
    cancelled = jobs.cancel(sid, job["id"])
    assert cancelled["status"] == "cancelled"
    with pytest.raises(ValueError, match="Cancelled"):
        await jobs.advance(sid, job["id"])


def test_api_cross_series_isolation_and_explicit_job_start(sample):
    sid, source, _, _, _ = sample
    foreign = vault.create_series("Elsewhere")["id"]
    with TestClient(app) as client:
        start = client.post(
            f"/api/series/{sid}/extraction-jobs",
            json={"source_id": source["id"], "model": "local-test"},
        )
        assert start.status_code == 201, start.text
        job = start.json()
        assert job["candidate_count"] == 0
        assert job["auto_canon_approved"] is False
        assert client.get(f"/api/series/{foreign}/extraction-jobs/{job['id']}").status_code == 404
        assert client.post(
            f"/api/series/{foreign}/extraction-jobs",
            json={"source_id": source["id"], "model": "local-test"},
        ).status_code == 404
        assert len(client.get(f"/api/series/{sid}/extraction-jobs").json()) == 1
        assert client.post(f"/api/series/{sid}/extraction-jobs/{job['id']}/cancel").json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_malformed_model_candidates_are_not_persisted(sample, monkeypatch):
    sid, source, text, mira, _ = sample

    async def compromised_adapter(series_id, source_id, start, end, model):
        return {"suggestions": [
            {"source_id": source_id, "quote_start": 0, "quote_end": 16,
             "quote": "This quote is invented", "subject_id": mira["id"],
             "predicate": "trusts", "object_text": "Rowan",
             "scope": "world", "knower_id": None},
            {"source_id": source_id, "quote_start": 0, "quote_end": 17,
             "quote": text[:17], "subject_id": "different-series-id",
             "predicate": "trusts", "object_text": "Rowan",
             "scope": "world", "knower_id": None},
            {"source_id": source_id, "quote_start": 0, "quote_end": 17,
             "quote": text[:17], "subject_id": mira["id"],
             "predicate": "trusts", "object_text": "Rowan",
             "scope": "world", "knower_id": None},
        ], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", compromised_adapter)
    job = jobs.create(sid, source["id"], "local-test")
    first = await jobs.advance(sid, job["id"])
    assert first["discarded"] == 2
    assert first["candidate_count"] == 1
    assert first["candidates"][0]["quote"] == text[:17]
    assert not canon.list_facts(sid)


@pytest.mark.asyncio
async def test_expired_running_lease_recovers_exact_same_window(sample, monkeypatch):
    sid, source, _, _, _ = sample
    calls = []

    async def fake_suggest(series_id, source_id, start, end, model):
        calls.append((start, end))
        return {"suggestions": [], "discarded": 0}

    monkeypatch.setattr(suggestions, "suggest_facts", fake_suggest)
    job = jobs.create(sid, source["id"], "local-test")
    with vault._connect() as con:
        con.execute(
            "UPDATE series_extraction_jobs SET status='running',leased_at=? WHERE id=?",
            ("2020-01-01T00:00:00+00:00", job["id"]),
        )
    result = await jobs.advance(sid, job["id"])
    assert calls and calls[0][0] == 0
    assert result["processed_windows"] == 1
    assert result["next_offset"] == calls[0][1]
