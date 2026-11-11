"""Fetch public submission pages and preserve evidence for author review."""
import ipaddress
import re
import socket
from http.client import HTTPSConnection
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

MAX_BYTES = 1_000_000
RULES = re.compile(
    r"submit|submission|query|synopsis|manuscript|chapters?|pages?|words?|deadline|"
    r"anonymous|blind|\.docx?|\.pdf|attachment|\bAI\b|artificial intelligence",
    re.IGNORECASE,
)


def fetch_html(url: str) -> bytes:
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
