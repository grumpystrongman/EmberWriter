from __future__ import annotations

import json
import re
import shutil
from pathlib import PurePosixPath

from .binder import sync_binder
from .project_recovery import _restore_missing_manuscript_from_history
from .storage import create_project, get_project, project_root

_SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _normalize_relative_path(value: str) -> PurePosixPath:
    raw = value.strip()
    normalized = raw.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"Unsafe project path: {value}")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe project path: {value}")
    if any(part.casefold() in _SKIP_PARTS for part in path.parts):
        raise ValueError(f"Project folder contains an unsupported technical path: {value}")
    return path


def _strip_common_folder(paths: list[PurePosixPath]) -> list[PurePosixPath]:
    if not paths:
        return []
    first_parts = [path.parts[0] for path in paths if path.parts]
    if not first_parts or len(first_parts) != len(paths):
        return paths
    common = first_parts[0]
    if not all(part == common for part in first_parts):
        return paths
    if not all(len(path.parts) >= 2 for path in paths):
        return paths
    return [PurePosixPath(*path.parts[1:]) for path in paths]


def _source_metadata(entries: list[tuple[PurePosixPath, bytes]]) -> dict:
    for path, data in entries:
        if path.as_posix() != "project.json":
            continue
        try:
            payload = json.loads(data.decode("utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def restore_uploaded_project(
    entries: list[tuple[str, bytes]],
    *,
    name: str | None = None,
) -> dict:
    if not entries:
        raise ValueError("Choose an EmberWriter project folder")

    paths = [_normalize_relative_path(path) for path, _ in entries]
    paths = _strip_common_folder(paths)
    normalized = list(zip(paths, (data for _, data in entries), strict=True))

    has_project_meta = any(path.as_posix() == "project.json" for path, _ in normalized)
    has_manuscript = any(path.parts and path.parts[0] == "manuscript" for path, _ in normalized)
    has_ember_history = any(
        path.as_posix() == ".ember/story.db"
        or (len(path.parts) >= 3 and path.parts[:2] == (".ember", "snapshots"))
        for path, _ in normalized
    )
    if not (has_project_meta or has_manuscript or has_ember_history):
        raise ValueError(
            "That folder does not look like an EmberWriter project. Expected project.json, manuscript/, or .ember history."
        )

    source_meta = _source_metadata(normalized)
    fallback_name = "Recovered EmberWriter Project"
    if entries and paths:
        raw_first = _normalize_relative_path(entries[0][0])
        if len(raw_first.parts) > len(paths[0].parts):
            fallback_name = raw_first.parts[0]
    project_name = (name or str(source_meta.get("name") or fallback_name)).strip() or fallback_name
    description = str(source_meta.get("description") or "Restored from an EmberWriter project folder.")

    created = create_project(project_name, description)
    slug = created["slug"]
    root = project_root(slug)

    # create_project seeds helpful starter files. A restore must be exact instead
    # of mixing those defaults into the recovered author's work.
    for child in list(root.iterdir()):
        if child.name == "project.json":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    written = 0
    for relative, data in normalized:
        relative_text = relative.as_posix()
        if relative_text == "project.json":
            continue
        destination = root.joinpath(*relative.parts)
        if root not in destination.resolve().parents:
            raise ValueError(f"Path escapes project directory: {relative_text}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        written += 1

    meta_path = root / "project.json"
    target_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if isinstance(source_meta.get("content_profile"), dict):
        target_meta["content_profile"] = source_meta["content_profile"]
    target_meta["restored_from_upload"] = True
    target_meta["source_project_id"] = source_meta.get("id", "")
    meta_path.write_text(json.dumps(target_meta, indent=2), encoding="utf-8")

    history_restored = _restore_missing_manuscript_from_history(root)
    binder = sync_binder(slug)
    detail = get_project(slug)
    return {
        "project": detail,
        "binder": binder.model_dump(),
        "written_files": written,
        "history_restored": history_restored,
        "history_restored_count": len(history_restored),
    }