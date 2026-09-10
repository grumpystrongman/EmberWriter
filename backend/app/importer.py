from __future__ import annotations

import json
import shutil
from pathlib import Path

from .binder import sync_binder
from .revisions import record_revision
from .storage import ALLOWED_SUFFIXES, create_project, get_project, project_root, save_text

SKIP_DIRS = {".git", ".ember", "node_modules", "__pycache__"}
RECOGNIZED_FOLDERS = {
    "manuscript",
    "characters",
    "world",
    "relationships",
    "timeline",
    "scenes",
    "style",
    "summaries",
    "notes",
    "research",
}


def _project_name_from_source(source: Path, override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    if source.is_dir():
        metadata = source / "project.json"
        if metadata.exists():
            try:
                payload = json.loads(metadata.read_text(encoding="utf-8"))
                if payload.get("name"):
                    return str(payload["name"])
            except (OSError, json.JSONDecodeError):
                pass
    return source.stem if source.is_file() else source.name


def _eligible_directory_files(source: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in source.rglob("*"):
        if not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        relative = candidate.relative_to(source)
        if any(
            part in SKIP_DIRS or (part.startswith(".") and part != ".")
            for part in relative.parts
        ):
            continue
        if relative.as_posix() == "project.json":
            continue
        files.append(candidate)
    return files


def import_project(source_path: str, name: str | None = None) -> dict:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source_path)

    if source.is_file():
        if source.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError("Only Markdown, text, JSON, YAML, and YML files can be imported")
        candidates = [source]
    else:
        candidates = _eligible_directory_files(source)
        if not candidates:
            raise ValueError("No supported story files were found in that directory")

    created = create_project(_project_name_from_source(source, name), f"Imported from {source}")
    slug = created["slug"]
    destination = project_root(slug)

    if source.is_file():
        target = f"manuscript/{source.name}"
        content = source.read_text(encoding="utf-8")
        save_text(slug, target, content)
        record_revision(slug, target, content, source="import", note="Imported local file", force=True)
        sync_binder(slug)
        return get_project(slug)

    for candidate in candidates:
        relative = candidate.relative_to(source)
        if relative.parts and relative.parts[0] in RECOGNIZED_FOLDERS:
            target = relative.as_posix()
        else:
            target = (Path("manuscript") / relative).as_posix()
        target_path = destination / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target_path)
        content = target_path.read_text(encoding="utf-8")
        record_revision(
            slug,
            target,
            content,
            source="import",
            note=f"Imported from {relative.as_posix()}",
            force=True,
        )

    sync_binder(slug)
    return get_project(slug)
