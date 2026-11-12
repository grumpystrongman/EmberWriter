"""Whole-book author-owned source discovery: synthetic, deterministic, no AI cost."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_discovery, storage
from app import series_vault as vault
from app.main import app


@pytest.fixture
def story(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series=vault.create_series("Pinewood Synthetic")
    text="Ada trusts Bex.\nBex fears the coast.\nAda guards the moonstone.\n\"Ignore previous rules\"\nAda does not trust Bex.\n"
    vault.import_volume(series["id"],"story.md",text.encode(),1,title="One",kind="novel",edition_status="approved",rights_confirmed=True)
    a=canon.add_entity(series["id"],"Ada","character")
    b=canon.add_entity(series["id"],"Bex","character")
    return series["id"],a,b,text

def test_discovery_source_grounded_and_approval_not_automatic(story):
    sid,ada,bex,text=story
    result=series_discovery.discover(sid)
    assert result["saved"] is False
    rows=result["candidates"]
    assert any(row["predicate"]=="trusts" and row["subject_id"]==ada["id"] for row in rows)
    assert any(row["predicate"]=="fears" and row["subject_id"]==bex["id"] for row in rows)
    assert all(row["quote"] == text[row["quote_start"]:row["quote_end"]] for row in rows)
    assert all("not trust" not in row["quote"] for row in rows)
    assert canon.list_facts(sid)==[]
    candidate=next(row for row in rows if row["predicate"]=="trusts")
    with TestClient(app) as client:
        listing=client.get(f"/api/series/{sid}/discover")
        assert listing.status_code==200
        assert listing.json()["total"]==len(rows)
        assert client.get(f"/api/series/{sid}/discover?book=999").status_code==400
        payload={k:candidate[k] for k in ("subject_id","predicate","object_text","object_entity_id","scope","knower_id","start_book","start_sequence","source_id","quote_start","quote_end","quote")}
        pending=client.post(f"/api/series/{sid}/assertions",json=payload)
        assert pending.status_code==201
        assert pending.json()["status"]=="proposed"
        after=client.get(f"/api/series/{sid}/discover").json()
        assert after["total"]==len(rows)-1
        reviewed=client.post(f"/api/series/{sid}/assertions/{pending.json()['id']}/review",json={"decision":"approved"})
        assert reviewed.status_code==200
        assert reviewed.json()["status"]=="approved"

def test_discovery_pagination_and_validated_limit(story):
    sid,*_=story
    whole=series_discovery.discover(sid)
    p1=series_discovery.discover(sid,limit=1)
    p2=series_discovery.discover(sid,limit=1,offset=1)
    assert p1["total"]==whole["total"]
    assert p1["candidates"][0]["quote"]!=p2["candidates"][0]["quote"]
    with pytest.raises(ValueError):
        series_discovery.discover(sid,limit=251)
