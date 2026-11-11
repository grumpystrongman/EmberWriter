import socket

import pytest

from app.submission_guidelines import extract_guidelines, fetch_html


def test_import_preserves_source_rules_and_suggests_sample():
    result = extract_guidelines(b"""
        <nav>Submit the first 99 pages.</nav>
        <main><p>Submit the first 10 pages.</p><p>AI-generated writing is ineligible.</p></main>
    """)
    assert result == {
        "text": "Submit the first 10 pages.\nAI-generated writing is ineligible.",
        "settings": {"sample_kind": "pages", "sample_count": 10},
    }


def test_import_does_not_select_between_competing_samples():
    result = extract_guidelines(b"<p>Send the first 5 pages or the first 2 chapters.</p>")
    assert result["settings"] == {}


def test_import_rejects_nonpublic_resolution(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ValueError, match="public address"):
        fetch_html("https://publisher.example/rules")


def test_weekly_market_refresh_retains_last_success(tmp_path, monkeypatch):
    from app import storage, submission_market

    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(submission_market, "PUBLISHERS", {"Press": "https://example.com/rules"})
    responses = iter([b"<p>Submit the first 10 pages.</p>", b"<p>Submit the first 5 pages.</p>"])
    monkeypatch.setattr(submission_market, "fetch_html", lambda url: next(responses))

    def expire_check():
        with submission_market._connect() as db:
            db.execute("UPDATE publisher_rules SET checked_at = '2000-01-01'")

    submission_market.refresh_due_publishers()
    submission_market.refresh_due_publishers()
    assert submission_market.market_listings()[0]["guidelines"]["settings"]["sample_count"] == 10
    expire_check()
    submission_market.refresh_due_publishers()
    changed = submission_market.market_listings()[0]
    assert changed["changed_at"]
    assert changed["guidelines"]["settings"]["sample_count"] == 5

    def unavailable(url):
        raise OSError("offline")

    expire_check()
    monkeypatch.setattr(submission_market, "fetch_html", unavailable)
    submission_market.refresh_due_publishers()
    offline = submission_market.market_listings()[0]
    assert offline["error"]
    assert offline["guidelines"] == changed["guidelines"]


def test_book_publisher_catalog_contains_thousands_of_distinct_records():
    from app.submission_market import book_publisher_catalog

    publishers = book_publisher_catalog()
    assert len(publishers) >= 2800
    assert len({publisher["wikidata_id"] for publisher in publishers}) == len(publishers)
    assert sum(bool(publisher["website"]) for publisher in publishers) >= 1600
