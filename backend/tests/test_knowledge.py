from pathlib import Path

import pytest

from app import knowledge, storage
from app.knowledge_models import (
    EmbeddingConfig,
    GrammarReviewRequest,
    KnowledgeSearchRequest,
)
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_seeded_knowledge_is_source_attributed_and_searchable(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    sources = knowledge.list_sources()
    assert any(item["id"] == "kdp-paperback-cover" for item in sources)
    assert any(item["id"] == "gmu-punctuation" for item in sources)

    results = knowledge.lexical_search("paperback cover bleed 300 DPI", ["publishing"], 10)
    assert results
    assert any(item["source_id"] == "kdp-paperback-cover" for item in results)
    assert all(item["source_url"].startswith("https://") for item in results)
    assert all(item["authority"] for item in results)


def test_due_source_ids_respect_each_source_refresh_cadence(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    knowledge.ensure_seeded()
    source_id = "kdp-paperback-cover"

    with knowledge._connect() as con:
        con.execute(
            "UPDATE knowledge_sources SET last_checked_at = ?, error = '' WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", source_id),
        )
    assert source_id in knowledge.due_source_ids()

    with knowledge._connect() as con:
        con.execute(
            "UPDATE knowledge_sources SET last_checked_at = ?, error = '' WHERE id = ?",
            (knowledge._now(), source_id),
        )
    assert source_id not in knowledge.due_source_ids()


@pytest.mark.asyncio
async def test_live_refresh_replaces_seed_without_reappearing(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    knowledge.ensure_seeded()

    html = b"""
    <html><body><main>
      <h1>Cover Image Tips</h1>
      <p>Kobo recommends portrait cover images for ebook storefront display and reader libraries.</p>
      <p>Use a high quality source image and verify the current file requirements before upload.</p>
      <p>This test page contains enough meaningful publishing text to exercise extraction and chunking.</p>
    </main></body></html>
    """

    class FakeResponse:
        def __init__(self) -> None:
            self.content = html
            self.headers = {"content-type": "text/html; charset=utf-8"}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str):
            assert "kobo" in url.casefold()
            return FakeResponse()

    monkeypatch.setattr(knowledge.httpx, "AsyncClient", FakeClient)
    result = await knowledge.refresh_source("kobo-cover")
    assert result["status"] == "updated"

    # Re-seeding happens on normal app/search access. It must not resurrect stale curated chunks after
    # a successfully refreshed source has replaced them.
    knowledge.ensure_seeded()
    with knowledge._connect() as con:
        rows = con.execute(
            "SELECT id FROM knowledge_chunks WHERE source_id = ? ORDER BY id", ("kobo-cover",)
        ).fetchall()
    assert rows
    assert all(":live:" in row["id"] for row in rows)


@pytest.mark.asyncio
async def test_failed_refresh_preserves_last_known_good_rules(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    before = knowledge.lexical_search("paperback cover bleed 300 DPI", ["publishing"], 20)
    before_ids = {item["id"] for item in before}
    assert before_ids

    class FailingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str):
            raise knowledge.httpx.ConnectError("offline")

    monkeypatch.setattr(knowledge.httpx, "AsyncClient", FailingClient)
    result = await knowledge.refresh_source("kdp-paperback-cover")
    assert result["status"] == "error"

    after = knowledge.lexical_search("paperback cover bleed 300 DPI", ["publishing"], 20)
    assert before_ids <= {item["id"] for item in after}
    source = next(item for item in knowledge.list_sources() if item["id"] == "kdp-paperback-cover")
    assert source["status"] == "error"
    assert "offline" in source["error"]


@pytest.mark.asyncio
async def test_embedding_index_and_semantic_search(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    knowledge.ensure_seeded()

    async def fake_embed(config: EmbeddingConfig, texts: list[str]) -> list[list[float]]:
        assert config.model == "test-embed"
        return [
            [1.0, 0.0, 0.0] if "cover" in text.casefold() else [0.0, 1.0, 0.0]
            for text in texts
        ]

    monkeypatch.setattr(knowledge, "_embed", fake_embed)
    config = EmbeddingConfig(model="test-embed")
    indexed = await knowledge.index_embeddings(config, ["publishing"], force=True)
    assert indexed["chunks_indexed"] > 0
    assert indexed["dimensions"] == 3

    unchanged = await knowledge.index_embeddings(config, ["publishing"], force=False)
    assert unchanged["chunks_indexed"] == 0
    assert unchanged["dimensions"] == 3

    with knowledge._connect() as con:
        row = con.execute(
            "SELECT id, body FROM knowledge_chunks WHERE category = 'publishing' ORDER BY id LIMIT 1"
        ).fetchone()
        new_body = f"{row['body']} Updated requirement text."
        con.execute(
            "UPDATE knowledge_chunks SET body = ?, content_hash = ? WHERE id = ?",
            (new_body, knowledge._digest(new_body), row["id"]),
        )
        knowledge._reindex_chunk(con, row["id"])

    changed = await knowledge.index_embeddings(config, ["publishing"], force=False)
    assert changed["chunks_indexed"] == 1

    results = await knowledge.search_knowledge(
        KnowledgeSearchRequest(
            query="cover",
            categories=["publishing"],
            limit=5,
            semantic=True,
            embedding=config,
        )
    )
    assert results
    assert results[0]["semantic_score"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_grammar_review_rejects_hallucinated_rule_ids(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    knowledge.ensure_seeded()

    async def fake_generate(*args, **kwargs) -> str:
        return (
            '{"summary":"One likely run-on.","issues":['
            '{"quote":"I ran, I fell.","rule_ids":["grammar-runon-comma-splice"],'
            '"explanation":"Two independent clauses are joined only by a comma.",'
            '"suggestion":"Use a period, semicolon, or conjunction.","confidence":0.98,'
            '"intentional_style_possible":false},'
            '{"quote":"I ran","rule_ids":["invented-rule"],"explanation":"fake",'
            '"suggestion":"fake","confidence":1.0,"intentional_style_possible":false}]}'
        )

    monkeypatch.setattr(knowledge, "generate", fake_generate)
    result = await knowledge.grammar_review(
        GrammarReviewRequest(
            text="I ran, I fell.",
            provider=ProviderConfig(model="test"),
        )
    )
    assert result["summary"] == "One likely run-on."
    assert len(result["issues"]) == 1
    assert result["issues"][0]["rule_ids"] == ["grammar-runon-comma-splice"]
