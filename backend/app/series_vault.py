"""Series Vault: local-first, rights-checked multi-book library with immutable evidence.

This module does not write to manuscript projects, scrape books, or send files to
external services. A volume's source snapshot is immutable; changed linked project
files are reported as stale and must be explicitly re-snapshotted in a new edition.
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import storage

MAX_IMPORT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENT_CHARS = 4_000_000
MAX_SOURCES_PER_VOLUME = 400
VALID_EDITION_STATUS = {"published", "approved", "draft", "reference"}
VALID_VOLUME_KIND = {"novel", "novella", "short_story", "companion", "notes", "other"}
FILE_EXTENSIONS = {".md", ".txt", ".docx", ".pdf", ".epub"}


def now() -> str:
    return datetime.now(UTC).isoformat()


def _root() -> Path:
    # Respect the same configurable data location used by isolated project tests.
    root = storage.PROJECTS_ROOT.parent / "series"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _id() -> str:
    return uuid4().hex


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(_root() / "series-vault.sqlite3", timeout=15)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS series (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS volumes (
            id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            title TEXT NOT NULL, ordinal INTEGER NOT NULL,
            kind TEXT NOT NULL, edition_status TEXT NOT NULL,
            project_slug TEXT, created_at TEXT NOT NULL,
            UNIQUE(series_id, ordinal)
        );
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, volume_id TEXT NOT NULL REFERENCES volumes(id) ON DELETE CASCADE,
            title TEXT NOT NULL, source_path TEXT NOT NULL, sequence INTEGER NOT NULL,
            snapshot_path TEXT NOT NULL, sha256 TEXT NOT NULL,
            bytes INTEGER NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(volume_id, source_path)
        );
        CREATE INDEX IF NOT EXISTS sources_volume_idx ON sources(volume_id, sequence);
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            name TEXT NOT NULL, kind TEXT NOT NULL, aliases TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            UNIQUE(series_id, name)
        );
        CREATE INDEX IF NOT EXISTS entity_series_idx ON entities(series_id);
        CREATE TABLE IF NOT EXISTS assertions (
            id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            subject_id TEXT NOT NULL REFERENCES entities(id),
            predicate TEXT NOT NULL, object_text TEXT NOT NULL DEFAULT '',
            object_entity_id TEXT REFERENCES entities(id),
            scope TEXT NOT NULL, knower_id TEXT REFERENCES entities(id),
            start_book INTEGER NOT NULL, start_sequence INTEGER NOT NULL DEFAULT 0,
            end_book INTEGER, end_sequence INTEGER,
            source_id TEXT REFERENCES sources(id), quote_start INTEGER,
            quote_end INTEGER, quote TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'proposed',
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            CHECK(status IN ('proposed', 'approved', 'rejected')),
            CHECK(scope IN ('world', 'character_belief', 'reader_reveal'))
        );
        CREATE INDEX IF NOT EXISTS assertion_lookup_idx ON assertions(
            series_id, subject_id, status, start_book, start_sequence
        );
        """)
        with con:
            yield con
    finally:
        con.close()


def _one(con: sqlite3.Connection, sql: str, args: tuple) -> dict:
    row = con.execute(sql, args).fetchone()
    if row is None:
        raise FileNotFoundError("Series, volume, source or entity not found")
    return dict(row)


def series_detail(series_id: str) -> dict:
    with _connect() as con:
        s = _one(con, "SELECT * FROM series WHERE id=?", (series_id,))
        volumes = [dict(v) for v in con.execute(
            "SELECT * FROM volumes WHERE series_id=? ORDER BY ordinal", (series_id,))]
        for volume in volumes:
            volume["sources"] = [dict(row) for row in con.execute(
                "SELECT id,title,source_path,sequence,sha256,bytes FROM sources "
                "WHERE volume_id=? ORDER BY sequence", (volume["id"],))]
            volume["source_count"] = len(volume["sources"])
        s["volumes"] = volumes
        return s


def list_series() -> list[dict]:
    with _connect() as con:
        return [dict(r) for r in con.execute("""
            SELECT series.*, COUNT(volumes.id) AS volume_count
            FROM series LEFT JOIN volumes ON volumes.series_id=series.id
            GROUP BY series.id ORDER BY series.created_at DESC""")]


def create_series(title: str, description: str = "") -> dict:
    title = title.strip()
    if not 1 <= len(title) <= 160 or len(description) > 2000:
        raise ValueError("A series needs a title of 1–160 characters")
    identifier = _id()
    with _connect() as con:
        con.execute("INSERT INTO series (id,title,description,created_at) VALUES (?,?,?,?)",
                    (identifier, title, description.strip(), now()))
    return series_detail(identifier)


def delete_series(series_id: str, confirmation: str) -> dict:
    """Explicitly delete only vault-owned series records and source snapshots.

    Never touches the original linked EmberWriter project, manuscripts, global
    style guides or independent series. Requires the exact series title.
    """
    with _connect() as con:
        entry = _one(con, "SELECT id,title FROM series WHERE id=?", (series_id,))
        if not confirmation or confirmation != entry["title"]:
            raise ValueError("Type the exact series title to confirm permanent deletion")
        volumes = [row["id"] for row in con.execute(
            "SELECT id FROM volumes WHERE series_id=?", (series_id,))]
        # Assertions refer to series-local entities and source IDs. Delete in
        # dependency order inside one SQLite transaction before touching files.
        con.execute("DELETE FROM assertions WHERE series_id=?", (series_id,))
        con.execute("DELETE FROM entities WHERE series_id=?", (series_id,))
        for volume_id in volumes:
            con.execute("DELETE FROM sources WHERE volume_id=?", (volume_id,))
        con.execute("DELETE FROM volumes WHERE series_id=?", (series_id,))
        con.execute("DELETE FROM series WHERE id=?", (series_id,))
    # Files are snapshots this vault created, under a validated generated ID.
    # Never recursively delete anything outside the controlled snapshots root.
    for volume_id in volumes:
        if re.fullmatch(r"[0-9a-f]{32}", volume_id):
            shutil.rmtree(_root() / "snapshots" / volume_id, ignore_errors=True)
    return {"deleted": True, "series_id": series_id,
            "linked_projects_deleted": False}


def _check_volume(ordinal: int, kind: str, edition_status: str, title: str) -> None:
    if not 1 <= ordinal <= 9999:
        raise ValueError("Book order must be between 1 and 9999")
    if kind not in VALID_VOLUME_KIND or edition_status not in VALID_EDITION_STATUS:
        raise ValueError("Unsupported volume type or edition status")
    if not 1 <= len(title.strip()) <= 180:
        raise ValueError("Volume title must be between 1 and 180 characters")


def _snapshot(volume_id: str, source_id: str, content: str) -> str:
    folder = _root() / "snapshots" / volume_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (source_id + ".txt")
    # Exclusive; immutable source snapshots cannot be silently replaced.
    with target.open("x", encoding="utf-8") as out:
        out.write(content)
    return target.relative_to(_root()).as_posix()


def _source_text(blob: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if len(blob) > MAX_IMPORT_BYTES:
        raise ValueError("The document exceeds the 25 MB local import limit")
    if extension in {".txt", ".md"}:
        value = blob.decode("utf-8-sig")
    elif extension == ".docx":
        from docx import Document
        document = Document(io.BytesIO(blob))
        value = "\n".join(p.text for p in document.paragraphs)
    elif extension == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(blob), strict=False)
        if len(reader.pages) > 1000:
            raise ValueError("PDF exceeds the 1,000-page import limit")
        value = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif extension == ".epub":
        from bs4 import BeautifulSoup
        from ebooklib import ITEM_DOCUMENT, epub
        book = epub.read_epub(io.BytesIO(blob))
        value = "\n\n".join(
            BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True)
            for item in book.get_items() if item.get_type() == ITEM_DOCUMENT
        )
    else:
        raise ValueError("Supported source files are TXT, Markdown, DOCX, EPUB and text-based PDF")
    if not value.strip():
        raise ValueError("Document contains no extractable text; scanned PDFs need OCR elsewhere")
    if len(value) > MAX_DOCUMENT_CHARS:
        raise ValueError("Extracted document exceeds the 4-million-character safety limit")
    return value


def _insert_volume(con: sqlite3.Connection, series_id: str, title: str,
                   ordinal: int, kind: str, status: str,
                   project_slug: str | None = None) -> str:
    _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
    _check_volume(ordinal, kind, status, title)
    identifier = _id()
    con.execute(
        "INSERT INTO volumes (id,series_id,title,ordinal,kind,edition_status,project_slug,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (identifier, series_id, title.strip(), ordinal, kind, status, project_slug, now()))
    return identifier


def attach_project(series_id: str, slug: str, ordinal: int, *, title: str | None,
                   kind: str, edition_status: str, rights_confirmed: bool) -> dict:
    if not rights_confirmed:
        raise ValueError("Confirm you have permission to include this project in the series")
    project = storage.get_project(slug)
    manuscript = sorted(
        p for p in project["files"] if p.startswith("manuscript/")
        and p.lower().endswith((".md", ".txt")))
    if not manuscript or len(manuscript) > MAX_SOURCES_PER_VOLUME:
        raise ValueError("Project must contain 1–400 manuscript documents")
    # Read everything before creating the volume; avoid partially attached projects.
    documents = []
    for path in manuscript:
        content = storage.read_text(slug, path)
        if content.strip() and len(content) <= MAX_DOCUMENT_CHARS:
            documents.append((path, content))
    if not documents:
        raise ValueError("Project contains no usable manuscript text")
    with _connect() as con:
        volume_id = _insert_volume(con, series_id, title or project["name"],
                                   ordinal, kind, edition_status, slug)
        for sequence, (path, content) in enumerate(documents, 1):
            source_id = _id()
            snapshot = _snapshot(volume_id, source_id, content)
            con.execute(
                "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
                (source_id, volume_id, Path(path).stem, path, sequence, snapshot,
                 hashlib.sha256(content.encode("utf-8")).hexdigest(),
                 len(content.encode("utf-8")), now()))
    return series_detail(series_id)


def import_volume(series_id: str, filename: str, blob: bytes, ordinal: int, *,
                  title: str | None, kind: str, edition_status: str,
                  rights_confirmed: bool) -> dict:
    if not rights_confirmed:
        raise ValueError("Confirm you own or are authorized to import this manuscript")
    if Path(filename).name != filename or len(filename) > 250:
        raise ValueError("Select a regular manuscript filename")
    extracted = _source_text(blob, filename)
    volume_title = title.strip() if title else Path(filename).stem
    with _connect() as con:
        volume_id = _insert_volume(con, series_id, volume_title, ordinal,
                                   kind, edition_status)
        source_id = _id()
        snapshot = _snapshot(volume_id, source_id, extracted)
        con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)",
                    (source_id, volume_id, Path(filename).stem, filename, 1,
                     snapshot, hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
                     len(extracted.encode("utf-8")), now()))
    return series_detail(series_id)


def update_volume(series_id: str, volume_id: str, *, title: str,
                  ordinal: int, kind: str, edition_status: str) -> dict:
    """Edit book organization without silently shifting established canon dates."""
    _check_volume(ordinal, kind, edition_status, title)
    with _connect() as con:
        volume = _one(con, "SELECT * FROM volumes WHERE id=? AND series_id=?",
                      (volume_id, series_id))
        if ordinal != volume["ordinal"]:
            linked_facts = con.execute("""
                SELECT 1 FROM assertions a
                LEFT JOIN sources s ON s.id=a.source_id
                LEFT JOIN volumes v ON v.id=s.volume_id
                WHERE a.series_id=? AND (
                    a.start_book=? OR a.end_book=? OR v.id=?
                ) LIMIT 1
            """, (series_id, volume["ordinal"], volume["ordinal"], volume_id)).fetchone()
            if linked_facts:
                raise ValueError(
                    "This volume is part of recorded canon history. Preserve its book order "
                    "or review the dependent assertions in a new series edition."
                )
        con.execute(
            "UPDATE volumes SET title=?, ordinal=?, kind=?, edition_status=? WHERE id=?",
            (title.strip(), ordinal, kind, edition_status, volume_id),
        )
    return series_detail(series_id)


def source_text(series_id: str, source_id: str) -> tuple[dict, str]:
    with _connect() as con:
        item = _one(con, """
            SELECT sources.*, volumes.series_id, volumes.ordinal, volumes.project_slug
            FROM sources JOIN volumes ON volumes.id=sources.volume_id
            WHERE sources.id=? AND volumes.series_id=?""", (source_id, series_id))
    base = _root().resolve()
    path = (base / item["snapshot_path"]).resolve()
    if base not in path.parents or not path.is_file():
        raise FileNotFoundError("Source snapshot is unavailable")
    content = path.read_text(encoding="utf-8")
    if hashlib.sha256(content.encode("utf-8")).hexdigest() != item["sha256"]:
        raise ValueError("Source snapshot checksum mismatch")
    return item, content


def volume_sources(series_id: str, volume_id: str) -> list[dict]:
    with _connect() as con:
        _one(con, "SELECT id FROM volumes WHERE id=? AND series_id=?",
             (volume_id, series_id))
        sources = [dict(r) for r in con.execute(
            "SELECT sources.* FROM sources WHERE volume_id=? ORDER BY sequence", (volume_id,))]
        volume = _one(con, "SELECT * FROM volumes WHERE id=?", (volume_id,))
    for row in sources:
        row["linked_project_changed"] = False
        if volume["project_slug"]:
            try:
                current = storage.read_text(volume["project_slug"], row["source_path"])
                row["linked_project_changed"] = hashlib.sha256(
                    current.encode("utf-8")).hexdigest() != row["sha256"]
            except (FileNotFoundError, ValueError):
                row["linked_project_changed"] = True
    return sources


def list_source_excerpt(series_id: str, source_id: str, query: str = "",
                        limit: int = 1200) -> dict:
    item, content = source_text(series_id, source_id)
    if not 120 <= limit <= 5000:
        raise ValueError("Excerpt limit must be 120–5,000 characters")
    at = content.casefold().find(query.strip().casefold()) if query.strip() else 0
    if at < 0:
        return {"source": item, "found": False, "excerpt": ""}
    begin = max(0, at - 200)
    end = min(len(content), begin + limit)
    return {"source": item, "found": True, "excerpt": content[begin:end],
            "excerpt_start": begin, "excerpt_end": end,
            "total_characters": len(content)}
