"""Exact EPUB ToC fragment coordinates derived from the original HTML parse.

A ToC anchor is accepted only if it has one unique id and maps directly to a
nonempty text node in the exact importer-normalized document. Never search for
repeated prose to approximate an offset; ambiguous links are discarded.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

MAX_TOC_LINKS = 1500


def _links(nodes):
    """Flatten nested ebooklib toc Link/Section tuples without relying on labels."""
    if isinstance(nodes, (list, tuple)):
        for item in nodes:
            yield from _links(item)
    else:
        href = getattr(nodes, "href", None)
        title = getattr(nodes, "title", None)
        if isinstance(href, str) and isinstance(title, str) and title.strip():
            yield href, title.strip()


def _text_starts(soup: BeautifulSoup, content: str) -> dict[int, int]:
    # _all_strings uses the same NavigableString filtering as get_text().
    # Index object identities so repeated chapter titles cannot cause false
    # offsets, and compare the entire normalized reconstruction.
    starts = {}
    chunks = []
    cursor = 0
    for node in soup._all_strings(strip=False):
        value = str(node).strip().translate({0x00AD: None, 0x200B: None, 0xFEFF: None})
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        if not value:
            continue
        if chunks:
            cursor += 1
        starts[id(node)] = cursor
        chunks.append(value)
        cursor += len(value)
    if " ".join(chunks) != content:
        return {}
    return starts


def toc_rows(book, extracted, offsets, *, max_rows: int) -> list[dict]:
    by_path = {item.file_name: (item, content) for item, content in extracted}
    by_basename = {}
    for path in by_path:
        by_basename.setdefault(PurePosixPath(path).name, []).append(path)
    soups = {}
    starts = {}
    grouped = {}
    seen = set()
    count = 0

    for href, label in _links(book.toc):
        count += 1
        if count > MAX_TOC_LINKS:
            break
        if len(label) > 120 or not href or "#" not in href:
            continue
        try:
            parts = urlsplit(href)
        except ValueError:
            continue
        if parts.scheme or parts.netloc or not parts.fragment:
            continue
        path = unquote(parts.path)
        fragment = unquote(parts.fragment)
        if not fragment or len(fragment) > 150:
            continue
        if path in by_path:
            matched_path = path
        else:
            # In some EPUBs ToC paths carry a content-root prefix that
            # ebooklib removed from item.file_name. Only unique basenames
            # can be reconciled; ambiguity must fail closed.
            options = by_basename.get(PurePosixPath(path).name, [])
            if len(options) != 1:
                continue
            matched_path = options[0]
        item, content = by_path[matched_path]
        if item.id not in offsets or (matched_path, fragment) in seen:
            continue
        seen.add((matched_path, fragment))
        if matched_path not in soups:
            soups[matched_path] = BeautifulSoup(item.get_content(), "html.parser")
            starts[matched_path] = _text_starts(soups[matched_path], content)
        soup = soups[matched_path]
        positions = starts[matched_path]
        if not positions:
            continue
        matches = soup.find_all(id=fragment)
        # Some EPUB 2 publications use <a name="chapter"> rather than id.
        matches += [tag for tag in soup.find_all(attrs={"name": fragment})
                    if tag not in matches and tag.name == "a"]
        if len(matches) != 1:
            continue
        offset = None
        for node in matches[0].next_elements:
            if id(node) in positions:
                offset = offsets[item.id][0] + positions[id(node)]
                break
        if offset is None or not offsets[item.id][0] <= offset < offsets[item.id][1]:
            continue
        grouped.setdefault(matched_path, []).append((offset, label, href, fragment))

    results = []
    for path, entries in grouped.items():
        item, _ = by_path[path]
        document_end = offsets[item.id][1]
        ordered = sorted(entries, key=lambda entry: entry[0])
        # Multiple ToC labels at an identical offset cannot be distinguished.
        # Retain first grounded anchor, never create zero-length segments.
        unique = []
        used_offsets = set()
        for entry in ordered:
            if entry[0] not in used_offsets:
                unique.append(entry)
                used_offsets.add(entry[0])
        for index, (offset, label, href, fragment) in enumerate(unique):
            end = unique[index + 1][0] if index + 1 < len(unique) else document_end
            if not offset < end:
                continue
            results.append({
                "title": label,
                "start": offset, "end": end, "characters": end - offset,
                "source_item": path, "toc_href": href, "toc_fragment": fragment,
                "heading_detected": False,
                "confidence": "exact_epub_toc_fragment",
                "author_confirmed": False,
            })
            if len(results) >= max_rows:
                return results
    return results
