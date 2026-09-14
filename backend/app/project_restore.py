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


def _looks_like_project(entries: list[tuple[PurePosixPath, bytes]]) -> bool:
    has_project_meta = any(path.as_posix() == "project.json" for path, _ in entries)
    has_manuscript = any(path.parts and path.parts[0].casefold() == "manuscript" for path, _ in entries)
    has_ember_history = any(
        path.as_posix().casefold() == ".ember/story.db"
        or (
            len(path.parts) >= 3
            and tuple(part.casefold() for part in path.parts[:2]) == (".ember", "snapshots")
        )
        for path, _ in entries
    )
    return has_project_meta or has_manuscript or has_ember_history


def _candidate_project_prefixes(paths: list[PurePosixPath]) -> list[tuple[str, ...]]:
    """Find project roots anywhere beneath the selected folder.

    Browser directory uploads include the selected folder name in every
    webkitRelativePath. If an author selects `data/projects`, paths look like
    `projects/my-book/project.json`; if they select `my-book`, they look like
    `my-book/project.json`. Detect the project root from the project artifacts
    themselves instead of assuming exactly one wrapper directory.
    """

    scores: dict[tuple[str, ...], int] = {}

    for path in paths:
        parts = path.parts
        lower = tuple(part.casefold() for part in parts)
        if not parts:
            continue

        if path.name.casefold() == "project.json" and ".ember" not in lower[:-1]:
            prefix = parts[:-1]
            scores[prefix] = max(scores.get(prefix, 0), 3)

        if len(parts) >= 2 and lower[-2:] == (".ember", "story.db"):
            prefix = parts[:-2]
            scores[prefix] = max(scores.get(prefix, 0), 2)

        for index, part in enumerate(lower[:-1]):
            if part == "manuscript":
                prefix = parts[:index]
                scores[prefix] = max(scores.get(prefix, 0), 1)
                break

    if not scores:
        return []

    # If a selected folder is itself a project, do not also treat nested copies
    # or archives as separate projects. For a library folder, sibling project
    # prefixes remain independent and are all returned.
    prefixes = sorted(scores, key=lambda item: (len(item), tuple(part.casefold() for part in item)))
    selected: list[tuple[str, ...]] = []
    for prefix in prefixes:
        if any(len(parent) <= len(prefix) and prefix[: len(parent)] == parent for parent in selected):
            continue
        selected.append(prefix)
    return selected


def _entries_under_prefix(
    entries: list[tuple[PurePosixPath, bytes]],
    prefix: tuple[str, ...],
) -> list[tuple[PurePosixPath, bytes]]:
    result: list[tuple[PurePosixPath, bytes]] = []
    prefix_length = len(prefix)
    for path, data in entries:
        if path.parts[:prefix_length] != prefix:
            continue
        relative_parts = path.parts[prefix_length:]
        if not relative_parts:
            continue
        result.append((PurePosixPath(*relative_parts), data))
    return result


def _reuse_existing_project(source_meta: dict) -> dict | None:
    source_slug = str(source_meta.get("slug") or "").strip()
    source_id = str(source_meta.get("id") or "").strip()
    if not source_slug or not source_id:
        return None

    try:
        root = project_root(source_slug)
    except ValueError:
        return None
    meta_path = root / "project.json"
    if not meta_path.exists():
        return None

    try:
        existing_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if str(existing_meta.get("id") or "") != source_id:
        return None

    history_restored = _restore_missing_manuscript_from_history(root)
    binder = sync_binder(source_slug)
    return {
        "project": get_project(source_slug),
        "binder": binder.model_dump(),
        "written_files": 0,
        "history_restored": history_restored,
        "history_restored_count": len(history_restored),
        "reused_existing": True,
    }


def _restore_root_relative_project(
    entries: list[tuple[PurePosixPath, bytes]],
    *,
    name: str | None,
    fallback_name: str,
) -> dict:
    if not _looks_like_project(entries):
        raise ValueError(
            "That folder does not look like an EmberWriter project. Expected project.json, manuscript/, or .ember history."
        )

    source_meta = _source_metadata(entries)
    existing = _reuse_existing_project(source_meta)
    if existing is not None:
        return existing

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
    for relative, data in entries:
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
        "reused_existing": False,
    }


def restore_uploaded_projects(
    entries: list[tuple[str, bytes]],
    *,
    name: str | None = None,
) -> dict:
    """Restore one EmberWriter project or every project beneath a library folder."""

    if not entries:
        raise ValueError("Choose an EmberWriter project or projects library folder")

    normalized = [(_normalize_relative_path(path), data) for path, data in entries]
    prefixes = _candidate_project_prefixes([path for path, _ in normalized])
    if not prefixes:
        raise ValueError(
            "No EmberWriter project was found in that folder. Select a project folder or the data/projects folder that contains your projects."
        )

    results: list[dict] = []
    multiple = len(prefixes) > 1
    for prefix in prefixes:
        project_entries = _entries_under_prefix(normalized, prefix)
        if not _looks_like_project(project_entries):
            continue
        fallback_name = prefix[-1] if prefix else "Recovered EmberWriter Project"
        results.append(
            _restore_root_relative_project(
                project_entries,
                name=None if multiple else name,
                fallback_name=fallback_name,
            )
        )

    if not results:
        raise ValueError(
            "No loadable EmberWriter project was found in that folder. Expected project.json, manuscript/, or .ember history."
        )

    history_restored = [
        item
        for result in results
        for item in result.get("history_restored", [])
    ]
    projects = [result["project"] for result in results]
    return {
        "project": projects[0],
        "projects": projects,
        "loaded_count": len(projects),
        "reused_count": sum(1 for result in results if result.get("reused_existing")),
        "written_files": sum(int(result.get("written_files", 0)) for result in results),
        "history_restored": history_restored,
        "history_restored_count": len(history_restored),
        "results": results,
    }


def restore_uploaded_project(
    entries: list[tuple[str, bytes]],
    *,
    name: str | None = None,
) -> dict:
    """Compatibility wrapper for callers that expect exactly one project."""

    bundle = restore_uploaded_projects(entries, name=name)
    if bundle["loaded_count"] != 1:
        raise ValueError(
            "That folder contains multiple EmberWriter projects. Load the projects library through the Load / Import control instead."
        )
    return bundle["results"][0]
