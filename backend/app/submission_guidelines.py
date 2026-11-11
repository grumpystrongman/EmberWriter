"""Fetch public submission pages and preserve evidence for author review."""
import ipaddress
import re
import socket
from http.client import HTTPException, HTTPSConnection
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

MAX_BYTES = 1_000_000
RULES = re.compile(
    r"submit|submission|query|synopsis|manuscript|chapters?|pages?|words?|deadline|"
    r"anonymous|blind|\.docx?|\.pdf|attachment|\bAI\b|artificial intelligence",
    re.IGNORECASE,
)


def _publisher_host(host: str | None) -> str:
    return (host or "").casefold().removeprefix("www.")


def fetch_html(url: str, redirects: int = 2) -> bytes:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
        or parsed.password is not None or parsed.port not in (None, 443)
    ):
        raise ValueError("Enter a public HTTPS guidelines URL.")
    host = parsed.hostname.encode("idna").decode("ascii")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = [address[4][0] for address in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("The guidelines URL must resolve to a public address.")

    connection = HTTPSConnection(host, timeout=8)

    # Pin the validated address while preserving TLS verification for the hostname.
    def connect_to_public_address(_address, timeout, source_address):
        return socket.create_connection((ips[0], 443), timeout, source_address)

    connection._create_connection = connect_to_public_address
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        connection.request("GET", path, headers={"Accept": "text/html"})
        response = connection.getresponse()
        if 300 <= response.status < 400:
            location = response.getheader("Location")
            target = urljoin(url, location) if location else ""
            if redirects and target and _publisher_host(urlsplit(target).hostname) == _publisher_host(host):
                connection.close()
                return fetch_html(target, redirects - 1)
            raise ValueError("Open the redirected page and import its final HTTPS URL.")
        if response.status != 200 or response.headers.get_content_type() != "text/html":
            raise ValueError("This page could not be imported. Paste its requirements manually.")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("This page exceeds the import size limit. Paste the relevant requirements.")
        return body
    finally:
        connection.close()


def extract_guidelines(body: bytes) -> dict:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    excerpts = list(dict.fromkeys(
        text for tag in main.find_all(["p", "li", "h2", "h3"])
        if (text := tag.get_text(" ", strip=True)) and RULES.search(text)
    ))
    if not excerpts:
        raise ValueError("No submission rules were identified. Paste the relevant requirements.")
    text = "\n".join(excerpts)
    if len(text) > 24000:
        text = text[:24000]
        text = text.rsplit("\n", 1)[0] or text
    samples = set(re.findall(
        r"\bfirst\s+(\d{1,5})\s+(pages?|chapters?|words?)\b", text, re.IGNORECASE,
    ))
    settings = {}
    if len(samples) == 1:
        count, unit = next(iter(samples))
        if int(count) > 0:
            settings = {"sample_kind": unit.lower().rstrip("s") + "s", "sample_count": int(count)}
    return {"text": text, "settings": settings}


SUBMISSION_LINK = re.compile(
    r"\b(submissions?|submit (?:your|a) (?:book|manuscript)|publish with us|"
    r"manuscript guidelines|for authors)\b", re.IGNORECASE,
)
MANUSCRIPT_RULE = re.compile(
    r"\b(manuscripts?|synopsis|query letter|sample (?:pages|chapters)|"
    r"unsolicited|literary agent|submission window)\b", re.IGNORECASE,
)


def discover_guidelines(website: str) -> list[dict]:
    """Return evidence from relevant public pages on the publisher's own site."""
    parsed = urlsplit(website)
    homepage = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    soup = BeautifulSoup(fetch_html(homepage), "html.parser")
    candidates: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        title = link.get_text(" ", strip=True)
        target = urlsplit(urljoin(homepage, link["href"]))
        if (
            not SUBMISSION_LINK.search(title)
            or target.scheme != "https"
            or _publisher_host(target.hostname) != _publisher_host(parsed.hostname)
        ):
            continue
        candidates[target._replace(fragment="").geturl()] = title

    results = []
    for url, title in list(candidates.items())[:4]:
        try:
            guidelines = extract_guidelines(fetch_html(url))
        except (OSError, ValueError, HTTPException):
            continue
        if MANUSCRIPT_RULE.search(guidelines["text"]):
            results.append({"url": url, "title": title, **guidelines})
    return results
