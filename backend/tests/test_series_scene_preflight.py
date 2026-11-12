"""Synthetic scene preflight: geography, condition and relationship evidence."""
import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_scene_preflight as preflight
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def world(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"PROJECTS_ROOT",tmp_path/"projects")
    s=vault.create_series("Synthetic Preflight")
    one="Alia remains in the Mountain Keep. Alia injured her ankle. Rowan distrusts Alia."
    two="Alia arrives at the Glass Harbor."
    for i,body in enumerate([one,two],1):
        vault.import_volume(s["id"],f"book-{i}.md",body.encode(),i,
                            title=f"Book {i}",kind="novel",edition_status="approved",rights_confirmed=True)
    sources=[v["sources"][0]["id"] for v in vault.series_detail(s["id"])["volumes"]]
    a=canon.add_entity(s["id"],"Alia","character")
    r=canon.add_entity(s["id"],"Rowan","character")
    keep=canon.add_entity(s["id"],"Mountain Keep","place")
    harbor=canon.add_entity(s["id"],"Glass Harbor","place")
    def approved(book,subject,predicate,phrase,value,target=None,accept=True):
        text=[one,two][book-1]
        index=text.index(phrase)
        f=canon.propose_fact(s["id"],subject["id"],predicate,object_text=value,
            object_entity_id=target["id"] if target else None,start_book=book,
            source_id=sources[book-1],quote_start=index,quote_end=index+len(phrase),quote=phrase)
        if accept:canon.review_fact(s["id"],f["id"],"approved")
    approved(1,a,"located_in","Alia remains in the Mountain Keep.","Mountain Keep",keep)
    approved(1,a,"injured","Alia injured her ankle.","ankle")
    approved(1,r,"distrusts","Rowan distrusts Alia.","Alia",a)
    approved(2,a,"located_in","Alia arrives at the Glass Harbor.","Glass Harbor",harbor,False)
    payload={
      "title":"Glass Harbor scene","book":1,"sequence":10,"objective":"Escape",
      "conflict":"Travel must be explained","opening":"","aftermath":"","voice_notes":"",
      "pov_id":a["id"],"location_id":harbor["id"],"participants":[a["id"],r["id"]],
      "beats":[{"id":"beat1","kind":"arrival","title":"Arrive","detail":"","pressure":30}],
    }
    return s["id"],payload


def test_preflight_flags_travel_as_reminder_with_exact_evidence(world):
    sid,payload=world
    with TestClient(app) as client:
        result=client.post(f"/api/series/{sid}/scene-preflight",json=payload)
        assert result.status_code==200,result.text
        body=result.json()
        assert body["read_only"] and not body["canon_modified"]
        assert body["staging_flags"]==1
        assert any(x["category"]=="condition" for x in body["checks"])
        assert any(x["category"]=="relationship" for x in body["checks"])
        staged=next(x for x in body["checks"] if x["category"]=="staging")
        assert "Mountain Keep" in staged["reason"]
        assert "travel may have happened" in staged["reason"]
        assert staged["quote"]=="Alia remains in the Mountain Keep."
        assert staged["reference"]["source_id"]


def test_preflight_does_not_promote_future_or_proposed_claims(world):
    sid,payload=world
    before=preflight.preflight(sid,payload)
    payload["book"]=2
    after=preflight.preflight(sid,payload)
    assert any(x["category"]=="staging" for x in before["checks"])
    assert any(x["category"]=="staging" for x in after["checks"])
    assert all(x["quote"]!="Alia arrives at the Glass Harbor." for x in after["checks"])
    assert canon.list_facts(sid,status="proposed")
