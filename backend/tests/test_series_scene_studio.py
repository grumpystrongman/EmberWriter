"""Synthetic scene-board persistence, conflicts, privacy and source-boundary tests."""
import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_scene_studio as studio
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"PROJECTS_ROOT",tmp_path/"projects")
    series=vault.create_series("Synthetic Scene Studio")
    vault.import_volume(series["id"],"first.md",b"Alia trusts Rowan. The keep falls at dusk.",1,
                        title="The Dusk Keep",kind="novel",edition_status="approved",rights_confirmed=True)
    alia=canon.add_entity(series["id"],"Alia","character")
    rowan=canon.add_entity(series["id"],"Rowan","character")
    keep=canon.add_entity(series["id"],"Dusk Keep","place")
    return series["id"],alia["id"],rowan["id"],keep["id"]


def specimen(alia,rowan,keep):
    return {
        "title":"Dusk confrontation","book":1,"sequence":20,
        "objective":"Find the hidden note","conflict":"A vow prevents disclosure",
        "opening":"Alia distrusts the silence","aftermath":"The team must separate",
        "voice_notes":"Clipped dialogue","pov_id":alia,"location_id":keep,
        "participants":[alia,rowan],
        "beats":[
            {"id":"a1","kind":"arrival","title":"Enter keep","detail":"Dark walls","pressure":25},
            {"id":"b2","kind":"reversal","title":"Truth uncovered","detail":"The vow","pressure":85},
        ],
    }


def test_scene_board_roundtrip_and_version_conflict(setup):
    series,alia,rowan,keep=setup
    payload=specimen(alia,rowan,keep)
    with TestClient(app) as client:
        endpoint=f"/api/series/{series}/scene-boards"
        created=client.post(endpoint,json=payload)
        assert created.status_code==201,created.text
        first=created.json()
        assert first["version"]==1
        assert len(client.get(endpoint+"?book=1").json())==1
        revision={**payload,"title":"Revision","version":1}
        response=client.put(endpoint+"/"+first["id"],json=revision)
        assert response.status_code==200,response.text
        assert response.json()["version"]==2
        assert client.put(endpoint+"/"+first["id"],json=revision).status_code==400
        assert client.post(endpoint+"/"+first["id"]+"/delete",json={"version":1}).status_code==400
        assert client.post(endpoint+"/"+first["id"]+"/delete",json={"version":2}).json()["deleted"]
        assert client.get(endpoint).json()==[]


def test_reject_invalid_character_bad_beat_and_wrong_series(setup):
    series,alia,rowan,keep=setup
    payload=specimen(alia,rowan,keep)
    payload["participants"]=["not-a-series-character"]
    assert pytest.raises(ValueError,studio.create_board,series,payload)
    payload["participants"]=[alia]
    payload["beats"][0]["pressure"]=111
    assert pytest.raises(ValueError,studio.create_board,series,payload)
    payload["beats"][0]["pressure"]=25
    payload["book"]=90
    assert pytest.raises(ValueError,studio.create_board,series,payload)
    payload["book"]=1
    other=vault.create_series("Other Synthetic")
    assert pytest.raises(ValueError,studio.create_board,other['id'],payload)


def test_no_automatic_canon_creation(setup):
    series,alia,rowan,keep=setup
    board=studio.create_board(series,specimen(alia,rowan,keep))
    assert board["aftermath"]=="The team must separate"
    assert canon.list_facts(series)==[]
    assert not (storage.PROJECTS_ROOT/"manuscript").exists()
