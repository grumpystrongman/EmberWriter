"""Chapter/section anchor detection without inventing in-world chronology."""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app import series_source_sections as structure
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic Source Sections")["id"]
    prose = ("Opening lines with no label.\n\n"
             "Chapter 1 - The Journey\nMira crossed the bridge.\n"
             "The word chapter occurred in a sentence, not as a heading.\n"
             "Chapter II\nRowan opened the gate.\n"
             "Epilogue\nMira returned.\n")
    details = vault.import_volume(
        sid, "journey.md", prose.encode(), 1, title="Journey",
        kind="novel", edition_status="reference", rights_confirmed=True,
    )
    src = details["volumes"][0]["sources"][0]["id"]
    return sid, src, prose


def test_exact_offsets_and_unverified_opening(library):
    sid, src, prose = library
    result = structure.sections(sid, src, position=prose.index("Rowan"))
    assert [s["heading_detected"] for s in result["sections"]] == [False, True, True, True]
    assert result["selected_section"] == 3
    assert result["story_sequence_inferred"] is False
    assert result["source_text_returned"] is False
    assert result["source_hash"] == hashlib.sha256(prose.encode()).hexdigest()
    for index, section in enumerate(result["sections"]):
        assert prose[section["start"]:section["end"]]
        assert section["end"] == (
            result["sections"][index+1]["start"]
            if index + 1 < len(result["sections"]) else len(prose)
        )
    assert result["sections"][1]["start"] == prose.index("Chapter 1")
    assert result["sections"][2]["start"] == prose.index("Chapter II")


def test_plain_prose_is_not_fake_chapters(library):
    sid, _, _ = library
    detail = vault.import_volume(
        sid, "plain.txt", b"A story without headings, but has many paragraphs.",
        2, title="Plain", kind="novel", edition_status="reference",
        rights_confirmed=True,
    )
    source = detail["volumes"][-1]["sources"][0]["id"]
    result = structure.sections(sid, source)
    assert len(result["sections"]) == 1
    assert not result["sections"][0]["author_confirmed"]
    assert not result["sections"][0]["heading_detected"]


def test_position_rejection_and_api_cross_series_isolation(library):
    sid, src, prose = library
    with TestClient(app) as client:
        response = client.get(f"/api/series/{sid}/sources/{src}/sections",
                              params={"position": prose.index("Mira returned")})
        assert response.status_code == 200
        assert response.json()["selected_section"] == 4
        assert client.get(f"/api/series/{sid}/sources/{src}/sections",
                          params={"position": len(prose)}).status_code == 400
        other = vault.create_series("Private Separate Source")["id"]
        assert client.get(
            f"/api/series/{other}/sources/{src}/sections"
        ).status_code == 404
