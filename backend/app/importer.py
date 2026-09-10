from __future__ import annotations

import json
import shutil
from pathlib import Path

from .storage import ALLOWED_SUFFIXES, create_project, get_project, project_root, save_text

SKIP_DIRS = {".git", ".ember", "node_modules", "__pycache__"}


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


def import_project(source_path: str, name: str | None = None) -> dict:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source_path)

    created = create_project(_project_name_from_source(source, name), f"Imported from {source}")
    slug = created["slug"]
    destination = project_root(slug)

    if source.is_file():
        if source.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError("Only Markdown, text, JSON, YAML, and YML files can be imported")
        target = f"manuscript/{source.name}"
        save_text(slug, target, source.read_text(encoding="utf-8"))
        return get_project(slug)

    imported = 0
    for candidate in source.rglob("*"):
        if not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        relative = candidate.relative_to(source)
        if any(part in SKIP_DIRS or (part.startswith(".") and part != ".") for part in relative.parts):
            continue
        if relative.as_posix() == "project.json":
            continue

        # Preserve recognized EmberWriter folders. Loose files go into manuscript/.
        if relative.parts and relative.parts[0] in {
            "manuscript", "characters", "world", "relationships", "timeline", "scenes", "style", "summaries"
        }:
            target = relative.as_posix()
        else:
            target = (Path("manuscript") / relative).as_posix()
        target_path = destination / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate, target_path)
        imported += 1

    if imported == 0:
        raise ValueError("No supported story files were found in that directory")
    return get_project(slug)
