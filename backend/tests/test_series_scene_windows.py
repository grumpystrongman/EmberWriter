"""Exact source reading windows: EPUB structure vs speculation kept separate."""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_epub_index as idx
from app import series_scene_windows as windows
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic Scene Segmentation")["id"]
    passage = ("Ada looked at the harbor and waited. A boat entered the channel.\n\n" * 125)
    content = "First chapter\n\n" + passage + "\n***\n" + passage + "\nSecond chapter\n\n" + passage
    volume = vault.import_volume(sid, "book.md", content.encode(), 1,
                                 title="One", kind="novel", edition_status="reference",
                                 rights_confirmed=True)
    source_id = volume["volumes"][0]["sources"][0]["id"]
    ada = canon.add_entity(sid, "Ada", "character")
    return sid, source_id, ada, content


def test_unindexed_windows_are_never_labeled_real_scenes(source):
    sid, _source_id, ada, content = source
    result = windows.scan(sid, book=1, limit=100)
    assert result["total"] > 3
    assert not result["auto_scene_approved"]
    assert all(not x["scene_confirmed"] and not x["pov_inferred"] for x in result["windows"])
    assert all(not x["confirmed_epub_structure"] for x in result["windows"])
    assert any(x["boundary_kind"]=="length_limited_reading_window" for x in result["windows"])
    for row in result["windows"]:
        assert 0 <= row["start"] < row["end"] <= len(content)
        assert row["length"] <= windows.WINDOW_LIMIT
        assert row["preview"] in content[row["start"]:row["end"]]
        assert row["range_hash"] == hashlib.sha256(
            content[row["start"]:row["end"]].encode()).hexdigest()
        assert row["character_mentions"][0]["entity_id"] == ada["id"]
    # Source breaks must not be fabricated into verified EPUB scene boundaries.
    assert windows.scan(sid, book=1, offset=1000)["windows"] == []


def test_confirmed_epub_sections_label_only_exact_metadata(source):
    sid, source_id, _ada, content = source
    boundary=content.index("Second chapter")
    record, _ = vault.source_text(sid,source_id)
    with vault._connect() as con:
        idx._table(con)
        con.execute("""
            INSERT INTO series_epub_structure_indexes
            (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
            VALUES (?,?,?,?,?,?)
        """, (source_id,sid,record["sha256"],"a"*64,
              json.dumps([
                  {"start":0,"end":boundary,"title":"Chapter One","index":1},
                  {"start":boundary,"end":len(content),"title":"Chapter Two","index":2},
              ]), vault.now()))
    result=windows.scan(sid,book=1,limit=100)
    assert any(r["section_title"]=="Chapter Two" and r["confirmed_epub_structure"]
               for r in result["windows"])
    assert all(not r["scene_confirmed"] for r in result["windows"])
    assert sum(r["length"] for r in result["windows"]) < len(content)  # Literal *** is metadata.
    first=result["windows"][0]
    detail=windows.detail(sid,book=1,source_id=source_id,start=first["start"],end=first["end"])
    assert detail["text"] == content[first["start"]:first["end"]]
    assert detail["range_hash"]==first["range_hash"]
    assert detail["source_verified"]
    with pytest.raises(ValueError,match="not a valid"):
        windows.detail(sid,book=1,source_id=source_id,start=first["start"]+1,end=first["end"])


def test_scene_route_book_isolation_and_invalid_coordinates(source):
    sid, source_id, _ada, content = source
    other=vault.create_series("Not shared")["id"]
    with TestClient(app) as client:
        api=f"/api/series/{sid}/scene-windows"
        result=client.get(api,params={"book":1,"limit":12})
        assert result.status_code==200,result.text
        row=result.json()["windows"][0]
        detail=client.get(f"{api}/{source_id}/detail",params={
            "book":1,"start":row["start"],"end":row["end"]})
        assert detail.status_code==200,detail.text
        assert detail.json()["text"]==content[row["start"]:row["end"]]
        assert client.get(api,params={"book":2}).json()["total"]==0
        assert client.get(api,params={"book":1,"limit":101}).status_code==422
        assert client.get(f"{api}/{source_id}/detail",params={
            "book":2,"start":row["start"],"end":row["end"]}).status_code==404
        assert client.get(f"/api/series/{other}/scene-windows/{source_id}/detail",
                          params={"book":1,"start":row["start"],"end":row["end"]}).status_code==404
        assert client.get(f"{api}/{source_id}/detail",params={
            "book":1,"start":row["start"],"end":row["end"]+1}).status_code==400
        assert canon.list_facts(sid)==[]


def test_author_scene_ledger_is_source_bound_and_not_canon(source):
    from app import series_scene_reviews as reviews
    sid, source_id, ada, _content = source
    window=windows.scan(sid,book=1)["windows"][0]
    staged=reviews.stage(sid,source_id=source_id,book=1,
                         start=window["start"],end=window["end"])
    assert staged["status"]=="proposed"
    assert not staged["author_confirmed_scene"]
    assert reviews.stage(sid,source_id=source_id,book=1,
                         start=window["start"],end=window["end"])["id"]==staged["id"]
    with pytest.raises(ValueError,match="classification and meaningful title"):
        reviews.decide(sid,staged["id"],decision="approved",
                       title="The harbor encounter")
    with pytest.raises(ValueError,match="POV character"):
        reviews.decide(sid,staged["id"],decision="approved",
                       title="The harbor encounter",kind="actual_scene",
                       pov_character_id="x"*32)
    accepted=reviews.decide(sid,staged["id"],decision="approved",
                            title="The harbor encounter",kind="actual_scene",
                            pov_style="third_limited",pov_character_id=ada["id"],
                            note="Author checked entire passage and narrative voice")
    assert accepted["source_verified"]
    assert accepted["author_confirmed_scene"]
    assert accepted["pov_character_id"]==ada["id"]
    assert canon.list_facts(sid)==[]
    foreign=vault.create_series("Another Author")["id"]
    with pytest.raises(FileNotFoundError):
        reviews.decide(foreign,staged["id"],decision="rejected")


def test_scene_review_api_requires_explicit_author_decision(source):
    sid, source_id, ada, _content=source
    window=windows.scan(sid,book=1)["windows"][0]
    with TestClient(app) as client:
        api=f"/api/series/{sid}/scene-reviews"
        assert client.get(api,params={"book":1}).json()==[]
        r=client.post(api,json={"source_id":source_id,"book":1,
                                "start":window["start"],"end":window["end"]})
        assert r.status_code==201,r.text
        rid=r.json()["id"]
        assert not r.json()["author_confirmed_scene"]
        assert client.post(f"{api}/{rid}/decision",json={"decision":"approved"}).status_code==400
        r=client.post(f"{api}/{rid}/decision",json={
            "decision":"approved","title":"A harbor scene","scene_kind":"actual_scene",
            "pov_style":"third_limited","pov_character_id":ada["id"]})
        assert r.status_code==200,r.text
        assert r.json()["author_confirmed_scene"]
        assert len(client.get(api,params={"book":1}).json())==1


def test_scene_review_portability_and_forged_range_rejection(source):
    import io
    import zipfile

    from app import series_portability as portability
    from app import series_scene_reviews as reviews
    sid, source_id, ada, _content = source
    window=windows.scan(sid,book=1)["windows"][0]
    staged=reviews.stage(sid,source_id=source_id,book=1,
                         start=window["start"],end=window["end"])
    reviews.decide(sid,staged["id"],decision="approved",
                   title="A harbor scene",kind="actual_scene",
                   pov_character_id=ada["id"])
    path=portability.backup(sid)
    try:
        raw=path.read_bytes()
        restored=portability.restore(raw,True)
        result=reviews.list_reviews(restored["id"])
        assert len(result)==1 and result[0]["author_confirmed_scene"]
        assert result[0]["source_id"]!=source_id
        assert result[0]["pov_character_id"]!=ada["id"]
        assert result[0]["pov_character_id"]==next(
            e["id"] for e in canon.list_entities(restored["id"]) if e["name"]=="Ada")
        with zipfile.ZipFile(io.BytesIO(raw)) as reader:
            entries={name:reader.read(name) for name in reader.namelist()}
        manifest=json.loads(entries["manifest.json"])
        manifest["author_scene_reviews"][0]["range_hash"]="0"*64
        entries["manifest.json"]=json.dumps(manifest).encode()
        forged=io.BytesIO()
        with zipfile.ZipFile(forged,"w") as writer:
            for name,data in entries.items():
                writer.writestr(name,data)
        with pytest.raises(ValueError,match="Scene review"):
            portability.restore(forged.getvalue(),True)
        manifest.pop("author_scene_reviews")
        entries["manifest.json"]=json.dumps(manifest).encode()
        older=io.BytesIO()
        with zipfile.ZipFile(older,"w") as writer:
            for name,data in entries.items():
                writer.writestr(name,data)
        restored_old=portability.restore(older.getvalue(),True)
        assert reviews.list_reviews(restored_old["id"])==[]
    finally:
        path.unlink(missing_ok=True)
