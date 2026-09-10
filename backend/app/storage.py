from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
DATA_ROOT = Path(os.getenv("EMBER_DATA_DIR", "data")).expanduser().resolve()
PROJECTS_ROOT = DATA_ROOT / "projects"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or f"project-{uuid4().hex[:8]}"


def ensure_data_root() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def project_root(slug: str) -> Path:
    ensure_data_root()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("Invalid project slug")
    root = (PROJECTS_ROOT / slug).resolve()
    if root.parent != PROJECTS_ROOT:
        raise ValueError("Invalid project path")
    return root


def safe_project_path(slug: str, relative_path: str) -> Path:
    root = project_root(slug)
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Path escapes project directory")
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Unsupported file type")
    return candidate


def _db_path(slug: str) -> Path:
    return project_root(slug) / ".ember" / "story.db"


def _connect(slug: str) -> sqlite3.Connection:
    path = _db_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            path TEXT NOT NULL,
            snapshot_path TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            kind TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            source_path TEXT,
            confidence REAL NOT NULL DEFAULT 1.0
        )
        """
    )
    con.commit()
    return con


def create_project(name: str, description: str = "") -> dict:
    ensure_data_root()
    base_slug = slugify(name)
    slug = base_slug
    suffix = 2
    while project_root(slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    root = project_root(slug)
    for folder in (
        "manuscript",
        "characters",
        "world",
        "relationships",
        "timeline",
        "scenes",
        "style",
        "summaries",
        ".ember/snapshots",
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)

    now = utc_now()
    metadata = {
        "schema_version": 1,
        "id": str(uuid4()),
        "slug": slug,
        "name": name.strip(),
        "description": description.strip(),
        "created_at": now,
        "updated_at": now,
        "content_profile": {
            "audience": "adult",
            "heat_level": "author_controlled",
            "language": "author_controlled",
            "all_intimate_participants_must_be_adults": True,
            "consent_required_for_erotic_content": True,
        },
    }
    (root / "project.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (root / "manuscript" / "chapter-001.md").write_text(
        f"# Chapter 1\n\nBegin {name.strip()} here.\n", encoding="utf-8"
    )
    (root / "summaries" / "rolling-summary.md").write_text(
        "# Rolling Summary\n\nNo story summary yet.\n", encoding="utf-8"
    )
    (root / "summaries" / "unresolved-threads.md").write_text(
        "# Unresolved Threads\n\n- None recorded yet.\n", encoding="utf-8"
    )
    (root / "style" / "author-profile.md").write_text(
        "# Author Profile\n\nDescribe preferred voice, pacing, POV, dialogue, and prose conventions here.\n",
        encoding="utf-8",
    )
    (root / "characters" / "README.md").write_text(
        "# Characters\n\nCreate one Markdown file per important character.\n", encoding="utf-8"
    )
    (root / "world" / "README.md").write_text(
        "# World Bible\n\nStore locations, factions, rules, magic, technology, and canon here.\n",
        encoding="utf-8",
    )
    _connect(slug).close()
    return get_project(slug)


def _metadata(slug: str) -> dict:
    path = project_root(slug) / "project.json"
    if not path.exists():
        raise FileNotFoundError(slug)
    return json.loads(path.read_text(encoding="utf-8"))


def _touch_project(slug: str) -> None:
    path = project_root(slug) / "project.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta["updated_at"] = utc_now()
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _iter_story_files(slug: str):
    root = project_root(slug)
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file() or ".ember" in path.parts:
            continue
        if path.suffix.lower() in ALLOWED_SUFFIXES:
            yield path


def list_projects() -> list[dict]:
    ensure_data_root()
    projects: list[dict] = []
    for directory in PROJECTS_ROOT.iterdir():
        if not directory.is_dir() or not (directory / "project.json").exists():
            continue
        try:
            meta = json.loads((directory / "project.json").read_text(encoding="utf-8"))
            projects.append(
                {
                    "slug": directory.name,
                    "name": meta.get("name", directory.name),
                    "description": meta.get("description", ""),
                    "updated_at": meta.get("updated_at", meta.get("created_at", "")),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(projects, key=lambda item: item["updated_at"], reverse=True)


def get_project(slug: str) -> dict:
    meta = _metadata(slug)
    root = project_root(slug)
    files = sorted(str(path.relative_to(root)).replace("\\", "/") for path in _iter_story_files(slug))
    return {
        "slug": slug,
        "name": meta.get("name", slug),
        "description": meta.get("description", ""),
        "updated_at": meta.get("updated_at", meta.get("created_at", "")),
        "files": files,
        "content_profile": meta.get("content_profile", {}),
    }


def read_text(slug: str, relative_path: str) -> str:
    path = safe_project_path(slug, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    return path.read_text(encoding="utf-8")


def save_text(slug: str, relative_path: str, content: str) -> dict:
    path = safe_project_path(slug, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_id = None

    if path.exists():
        snapshot_id = uuid4().hex
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        snapshot_rel = Path(".ember") / "snapshots" / stamp / relative_path
        snapshot_path = project_root(slug) / snapshot_rel
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, snapshot_path)
        with _connect(slug) as con:
            con.execute(
                "INSERT INTO snapshots (id, created_at, path, snapshot_path) VALUES (?, ?, ?, ?)",
                (snapshot_id, utc_now(), relative_path, str(snapshot_rel).replace("\\", "/")),
            )

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
    _touch_project(slug)
    return {"path": relative_path, "snapshot_id": snapshot_id}


def list_snapshots(slug: str, relative_path: str | None = None) -> list[dict]:
    with _connect(slug) as con:
        if relative_path:
            rows = con.execute(
                "SELECT id, created_at, path FROM snapshots WHERE path = ? ORDER BY created_at DESC LIMIT 100",
                (relative_path,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, created_at, path FROM snapshots ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
    return [dict(row) for row in rows]


def restore_snapshot(slug: str, snapshot_id: str) -> dict:
    with _connect(slug) as con:
        row = con.execute(
            "SELECT id, path, snapshot_path FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    if row is None:
        raise FileNotFoundError(snapshot_id)
    snapshot = project_root(slug) / row["snapshot_path"]
    if not snapshot.exists():
        raise FileNotFoundError(row["snapshot_path"])
    current_content = snapshot.read_text(encoding="utf-8")
    return save_text(slug, row["path"], current_content)


def search_story(slug: str, query: str, limit: int = 8) -> list[dict]:
    terms = {term for term in re.findall(r"[a-zA-Z0-9']+", query.lower()) if len(term) > 2}
    if not terms:
        return []
    hits: list[dict] = []
    for path in _iter_story_files(slug):
        relative = str(path.relative_to(project_root(slug))).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lowered = text.lower()
        matched = {term: lowered.count(term) for term in terms if term in lowered}
        if not matched:
            continue
        path_bonus = sum(2 for term in terms if term in relative.lower())
        score = float(sum(matched.values()) + path_bonus)
        first_positions = [lowered.find(term) for term in matched]
        start = max(0, min(first_positions) - 180)
        end = min(len(text), start + 700)
        excerpt = text[start:end].strip()
        hits.append({"path": relative, "score": score, "excerpt": excerpt})
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:limit]


def compile_context(
    slug: str,
    prompt: str = "",
    active_file: str | None = None,
    selected_text: str | None = None,
    max_chars: int = 48000,
) -> tuple[str, list[str]]:
    sections: list[str] = []
    used_files: list[str] = []
    seen: set[str] = set()

    def add_file(path: str, label: str | None = None, char_limit: int = 14000) -> None:
        if path in seen:
            return
        try:
            content = read_text(slug, path)
        except (FileNotFoundError, ValueError, OSError):
            return
        seen.add(path)
        used_files.append(path)
        sections.append(f"## {label or path}\nSource: {path}\n\n{content[:char_limit].strip()}")

    add_file("project.json", "Project settings", 6000)
    add_file("style/author-profile.md", "Author style", 7000)
    add_file("summaries/rolling-summary.md", "Rolling story summary", 9000)
    add_file("summaries/unresolved-threads.md", "Unresolved threads", 7000)
    if active_file:
        add_file(active_file, "Active manuscript", 18000)

    search_query = " ".join(part for part in (prompt, selected_text or "") if part).strip()
    if search_query:
        for hit in search_story(slug, search_query, limit=10):
            add_file(hit["path"], "Relevant story memory", 8000)

    if selected_text:
        sections.append(f"## Selected text\n\n{selected_text[:12000]}")

    context = "\n\n---\n\n".join(sections)
    if len(context) > max_chars:
        context = context[:max_chars]
    return context, used_files
