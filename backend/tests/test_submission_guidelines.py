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


def test_discovery_reads_only_same_publisher_submission_pages(monkeypatch):
    from app import submission_guidelines

    pages = {
        "https://publisher.example/": b"""
            <a href="/submissions">Submissions</a>
            <a href="https://elsewhere.example/apply">Submit your book</a>
            <a href="/newsletter">Newsletter</a>
        """,
        "https://publisher.example/submissions": b"<main><p>Submit the first 10 manuscript pages.</p></main>",
    }
    monkeypatch.setattr(submission_guidelines, "fetch_html", pages.__getitem__)
    results = submission_guidelines.discover_guidelines("http://publisher.example/")
    assert [entry["url"] for entry in results] == ["https://publisher.example/submissions"]
    assert "10 manuscript pages" in results[0]["text"]


def test_catalog_discovery_batches_and_schedules_found_sources(tmp_path, monkeypatch):
    from app import storage, submission_market

    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(submission_market, "PUBLISHERS", {})
    monkeypatch.setattr(submission_market, "book_publisher_catalog", lambda: [
        {"wikidata_id": "Q1", "name": "First Press", "website": "https://first.example"},
        {"wikidata_id": "Q2", "name": "Second Press", "website": "https://second.example"},
    ])
    seen = []

    def discover(site):
        seen.append(site)
        return [{"url": site + "/submit", "text": "Submit your manuscript.", "settings": {}}]

    monkeypatch.setattr(submission_market, "discover_guidelines", discover)
    submission_market.discover_due_publishers(limit=1)
    assert seen == ["https://first.example"]
    submission_market.discover_due_publishers(limit=1)
    assert seen == ["https://first.example", "https://second.example"]
    assert {row["url"] for row in submission_market.market_listings()} == {
        "https://first.example/submit", "https://second.example/submit",
    }


def test_public_fetch_falls_back_to_another_validated_address(monkeypatch):
    from email.message import Message
    from types import SimpleNamespace

    from app import submission_guidelines

    ips = ["2606:4700::1111", "1.1.1.1"]
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ips[0], 443, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", (ips[1], 443)),
    ])
    attempts = []

    def connect(address, timeout, source_address):
        attempts.append(address[0])
        if address[0] == ips[0]:
            raise OSError("IPv6 unavailable")

    headers = Message()
    headers["Content-Type"] = "text/html"

    class Connection:
        def __init__(self, host, timeout):
            assert host == "publisher.example"

        def request(self, method, path, headers):
            assert method == "GET" and path == "/submissions"
            self._create_connection(("publisher.example", 443), 8, None)

        def getresponse(self):
            return SimpleNamespace(status=200, headers=headers, read=lambda _: b"<p>Rules</p>")

        def close(self):
            pass

    monkeypatch.setattr(socket, "create_connection", connect)
    monkeypatch.setattr(submission_guidelines, "HTTPSConnection", Connection)
    assert fetch_html("https://publisher.example/submissions") == b"<p>Rules</p>"
    assert attempts == ips
