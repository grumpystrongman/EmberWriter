from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from . import storage
from .binder import sync_binder
from .project_recovery import (
    _candidate_project,
    _metadata_for_recovery,
    _restore_missing_manuscript_from_history,
)


def _project_candidates(source: Path) -> list[dict]:
    direct = _candidate_project(source)
    if direct is not None:
        return [direct]

    roots = [source]
    nested_projects = source / "projects"
    if nested_projects.is_dir():
        roots.insert(0, nested_projects)

    found: list[dict] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            try:
                resolved = child.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            item = _candidate_project(resolved)
            if item is None:
                continue
            found.append(item)
            seen.add(resolved)
    return found


def _active_project_by_id(project_id: str) -> tuple[str, Path] | None:
    if not project_id or not storage.PROJECTS_ROOT.exists():
        return None
    for directory in storage.PROJECTS_ROOT.iterdir():
        if not directory.is_dir():
            continue
        meta_path = directory / "project.json"
        if not meta_path.is_file():
            continue
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if str(payload.get("id") or "") == project_id:
            return directory.name, directory
    return None


def _ensure_visible_project(source: Path, item: dict) -> dict:
    slug = source.name
    meta_path = source / "project.json"
    if not meta_path.is_file():
        meta = _metadata_for_recovery(item, slug, source)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    history = _restore_missing_manuscript_from_history(source)
    binder = sync_binder(slug)
    return {
        "project": storage.get_project(slug),
        "binder": binder.model_dump(),
        "source_path": str(source),
        "target_path": str(source),
        "history_restored": history,
        "history_restored_count": len(history),
        "reused_existing": True,
        "copied": False,
    }


def _reuse_by_id(project_id: str) -> dict | None:
    match = _active_project_by_id(project_id)
    if match is None:
        return None
    slug, root = match
    history = _restore_missing_manuscript_from_history(root)
    binder = sync_binder(slug)
    return {
        "project": storage.get_project(slug),
        "binder": binder.model_dump(),
        "source_path": str(root),
        "target_path": str(root),
        "history_restored": history,
        "history_restored_count": len(history),
        "reused_existing": True,
        "copied": False,
    }


def _copy_project(source: Path, item: dict) -> dict:
    base_slug = storage.slugify(str(item.get("slug") or item.get("name") or source.name))
    target_slug = base_slug
    suffix = 2
    while (storage.PROJECTS_ROOT / target_slug).exists():
        target_slug = f"{base_slug}-loaded-{suffix}"
        suffix += 1

    target = storage.PROJECTS_ROOT / target_slug
    try:
        shutil.copytree(source, target)
        history = _restore_missing_manuscript_from_history(target)
        meta = _metadata_for_recovery(item, target_slug, source)
        (target / "project.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        binder = sync_binder(target_slug)
        project = storage.get_project(target_slug)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, sqlite3.Error):
        shutil.rmtree(target, ignore_errors=True)
        raise

    return {
        "project": project,
        "binder": binder.model_dump(),
        "source_path": str(source),
        "target_path": str(target),
        "history_restored": history,
        "history_restored_count": len(history),
        "reused_existing": False,
        "copied": True,
    }


def load_projects_from_path(source_path: str) -> dict:
    """Load one EmberWriter project or a projects library directly from local disk.

    This is intentionally server-side. It avoids pushing an existing local project
    through the browser as a potentially large multipart upload.
    """

    storage.ensure_data_root()
    source = Path(source_path).expanduser()
    if not source.exists():
        raise FileNotFoundError(source_path)
    if not source.is_dir():
        raise ValueError("Choose an EmberWriter project folder or projects library folder")
    source = source.resolve()

    candidates = _project_candidates(source)
    if not candidates:
        raise ValueError(
            "No EmberWriter project was found at that path. Expected project.json, manuscript/, or .ember history."
        )

    active_root = storage.PROJECTS_ROOT.resolve()
    results: list[dict] = []
    for item in candidates:
        project_source = Path(str(item["path"])).resolve()

        if project_source.parent == active_root:
            results.append(_ensure_visible_project(project_source, item))
            continue

        project_id = str(item.get("id") or "").strip()
        existing = _reuse_by_id(project_id)
        if existing is not None:
            existing["source_path"] = str(project_source)
            results.append(existing)
            continue

        results.append(_copy_project(project_source, item))

    projects = [result["project"] for result in results]
    history_restored = [
        entry
        for result in results
        for entry in result.get("history_restored", [])
    ]
    return {
        "project": projects[0],
        "projects": projects,
        "loaded_count": len(projects),
        "reused_count": sum(1 for result in results if result.get("reused_existing")),
        "copied_count": sum(1 for result in results if result.get("copied")),
        "history_restored": history_restored,
        "history_restored_count": len(history_restored),
        "source_path": str(source),
        "active_projects_root": str(storage.PROJECTS_ROOT),
        "results": results,
    }
