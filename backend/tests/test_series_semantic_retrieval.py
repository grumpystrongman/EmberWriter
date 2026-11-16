"""Synthetic tests for local incremental semantic retrieval."""
import pytest

from app import series_semantic_retrieval as semantic


@pytest.fixture
def corpus(monkeypatch, tmp_path):
    texts = {"a": "The agency shields citizens from hidden threats.",
             "b": "Later, the office defends the public in secret.",
             "c": "Future secrets must stay hidden."}
    detail = {"volumes": [
        {"ordinal": i, "title": str(i), "sources": [{"id": key, "sha256": key * 64}]}
        for i, key in enumerate(texts, 1)]}
    monkeypatch.setattr(semantic.vault, "_root", lambda: tmp_path)
    monkeypatch.setattr(semantic.vault, "series_detail", lambda _: detail)
    monkeypatch.setattr(semantic.vault, "source_text", lambda _, key: ({}, texts[key]))
    def hit(key):
        text = texts[key]
        return {"book": list(texts).index(key) + 1, "source_id": key,
                "excerpt_start": 0, "excerpt_end": len(text), "excerpt": text}
    return hit


def embedding(texts):
    return [[1.0, 0.0] if any(word in text.lower() for word in
            ("purpose", "shields", "defends")) else [0.0, 1.0] for text in texts]


def test_incremental_paraphrase_cutoff_and_reproducible(corpus):
    sid = "a" * 32
    semantic.retrieve(sid, "purpose", [corpus("a"), corpus("b"), corpus("c")],
                      max_book=3, embed=embedding)
    result = semantic.retrieve(sid, "purpose", [], max_book=2, embed=embedding)
    assert [row["source_id"] for row in result["results"]] == ["a", "b"]
    assert result["coverage"] == "incremental_windows_only"
    assert result["semantic_entailment"] == "unverified"
    assert result == semantic.retrieve(sid, "purpose", [], max_book=2, embed=embedding)
    later = semantic.retrieve(sid, "purpose", [], min_book=2, max_book=2, embed=embedding)
    assert [row["book"] for row in later["results"]] == [2]


def test_unavailable_and_invalid_offsets(corpus):
    invalid = dict(corpus("a"), excerpt_start=-1)
    wrong = dict(corpus("b"), book=1)
    def unavailable(_):
        raise ValueError("offline")
    result = semantic.retrieve("b" * 32, "purpose", [invalid, wrong, corpus("a")],
                               max_book=2, embed=unavailable)
    assert result["status"] == "semantic_unavailable"
    assert result["results"] == [corpus("a") | {"volume": "1"}]


def test_ties_are_stable_and_diverse(corpus):
    def ties(texts):
        return [[1, 1] for _ in texts]
    result = semantic.retrieve("c" * 32, "question", [corpus("b"), corpus("a")],
                               max_book=2, embed=ties)
    assert [row["book"] for row in result["results"]] == [1, 2]


def test_cloud_model_rejected():
    with pytest.raises(ValueError):
        semantic._embed(["synthetic"], "example:cloud")



def test_failed_local_embedding_avoids_repeat_waits(corpus, monkeypatch):
    import httpx
    calls = []
    def unavailable(texts, model):
        calls.append(1)
        raise httpx.ReadTimeout("offline")
    monkeypatch.setattr(semantic, "_embed", unavailable)
    monkeypatch.setattr(semantic, "_EMBED_UNAVAILABLE_UNTIL", 0.0)
    first = semantic.retrieve("d" * 32, "purpose", [corpus("a")], max_book=2)
    second = semantic.retrieve("d" * 32, "purpose", [corpus("a")], max_book=2)
    assert len(calls) == 1
    assert first["status"] == "semantic_unavailable"
    assert second["status"] == "embedding_model_cooldown"
    assert second["results"][0]["source_id"] == "a"
