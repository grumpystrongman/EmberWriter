import hashlib
import json

import pytest

from app import series_narrative_map as mapping

SID = "a" * 32


@pytest.fixture
def sources(tmp_path, monkeypatch):
    texts = {"one": "Mira trusts Sol. Mira knows the gate is open.",
             "two": "Sol betrayed Mira because he feared the king."}
    monkeypatch.setattr(mapping.vault, "_root", lambda: tmp_path)
    monkeypatch.setattr(mapping.vault, "series_detail", lambda _: {})

    def source(_, source_id):
        text = texts[source_id]
        return {"sha256": hashlib.sha256(text.encode()).hexdigest(),
                "ordinal": 1 if source_id == "one" else 2}, text

    monkeypatch.setattr(mapping.vault, "source_text", source)
    return texts


def claim(quote, **kwargs):
    return {"kind": "relation", "subject": "Mira", "predicate": "trusts",
            "object": "Sol", "scope": "narrator", "knower": "",
            "story_time": "unknown", "quote": quote, **kwargs}


@pytest.mark.asyncio
async def test_extract_review_and_no_future_leak(sources):
    async def generate(payload):
        assert payload['options']['num_predict'] == 900
        return json.dumps({'claims': [claim('Mira trusts Sol.'),
                                     claim('invented quote')]})
    job = mapping.create_job(SID, 'one', 'local')
    result = await mapping.advance(SID, job['id'], generate=generate)
    assert (result['accepted'], result['discarded'], result['complete']) == (1, 1, True)
    assert mapping.create_job(SID, 'one', 'local')['id'] == job['id']
    items = mapping.timeline(SID, 1)['items']
    assert items[0]['snapshot_verified'] and items[0]['status'] == 'proposed'
    assert mapping.timeline(SID, 1, source_offset=2)['items'] == []
    mapping.review(SID, items[0]['id'], 'confirmed_for_research')
    assert mapping.timeline(SID, 1)['items'][0]['status'] == 'confirmed_for_research'
    job2 = mapping.create_job(SID, 'two', 'local')
    async def second(_):
        return json.dumps({'claims': [claim('Sol betrayed Mira because he feared the king.',
                                            kind='cause', story_time='earlier')]})
    await mapping.advance(SID, job2['id'], generate=second)
    assert len(mapping.timeline(SID, 1)['items']) == 1
    assert len(mapping.timeline(SID, 2)['items']) == 2
    assert not mapping.timeline(SID, 2)['auto_canon_approved']


@pytest.mark.asyncio
async def test_failure_retry_knowledge_and_changed_snapshot(sources):
    job = mapping.create_job(SID, 'one', 'local')
    async def bad(_):
        return 'not json'
    with pytest.raises(ValueError):
        await mapping.advance(SID, job['id'], generate=bad)
    assert mapping.get_job(SID, job['id'])['next_offset'] == 0
    async def good(_):
        return json.dumps({'claims': [claim('Mira knows the gate is open.', kind='state',
                                            scope='character_knowledge', knower='Mira'),
                                      claim('Mira trusts Sol.', scope='character_knowledge')]})
    assert (await mapping.advance(SID, job['id'], generate=good))['accepted'] == 1
    item = mapping.timeline(SID, 1)['items'][0]
    assert item['knower'] == 'Mira'
    sources['one'] += ' changed'
    with pytest.raises(ValueError, match='snapshot'):
        mapping.review(SID, item['id'], 'confirmed_for_research')
    assert not mapping.timeline(SID, 1)['items'][0]['snapshot_verified']
