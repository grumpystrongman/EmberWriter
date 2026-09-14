from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from . import storage

_SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "AppData",
}


def _project_meta(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("name"), str):
        return None
    if not isinstance(payload.get("slug"), str):
        return None
    project_dir = path.parent
    if not (project_dir / "manuscript").exists():
        return None
    return payload


def _search_roots() -> list[Path]:
    candidates: list[Path] = []
    home = Path.home()
    repo_root = Path(__file__).resolve().parents[2]
    current = Path.cwd().resolve()

    env_roots = os.getenv("EMBER_RECOVERY_ROOTS", "")
    if env_roots:
        candidates.extend(Path(item).expanduser() for item in env_roots.split(os.pathsep) if item)

    candidates.extend(
        [
            home,
            home / "Documents",
            home / "Desktop",
            home / "Downloads",
            home / "source",
            home / "src",
            home / "repos",
            home / "projects",
            home / "dev",
            home / "code",
            repo_root.parent,
            current,
            current.parent,
        ]
    )

    one_drive = os.getenv("OneDrive") or os.getenv("ONEDRIVE")
    if one_drive:
        candidates.append(Path(one_drive))

    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.exists() or not resolved.is_dir():
            continue
        seen.add(resolved)
        roots.append(resolved)
    return roots


def discover_legacy_projects(max_results: int = 100, max_depth: int = 10) -> list[dict]:
    active_root = storage.PROJECTS_ROOT.resolve()
    discovered: list[dict] = []
    seen_dirs: set[Path] = set()

    for search_root in _search_roots():
        root_depth = len(search_root.parts)
        for dirpath, dirnames, filenames in os.walk(search_root, topdown=True):
            current = Path(dirpath)
            try:
                resolved = current.resolve()
            except OSError:
                dirnames[:] = []
                continue

            depth = len(resolved.parts) - root_depth
            if depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [name for name in dirnames if name not in _SKIP_DIR_NAMES]

            if resolved == active_root or active_root in resolved.parents:
                dirnames[:] = []
                continue
            if "project.json" not in filenames:
                continue
            if resolved in seen_dirs:
                continue

            meta = _project_meta(resolved / "project.json")
            if meta is None:
                continue
            seen_dirs.add(resolved)
            discovered.append(
                {
                    "path": str(resolved),
                    "name": meta.get("name", resolved.name),
                    "slug": meta.get("slug", resolved.name),
                    "id": meta.get("id", ""),
                    "updated_at": meta.get("updated_at", meta.get("created_at", "")),
                }
            )
            if len(discovered) >= max_results:
                return discovered
    return discovered


def _existing_project_ids() -> set[str]:
    ids: set[str] = set()
    if not storage.PROJECTS_ROOT.exists():
        return ids
    for project_dir in storage.PROJECTS_ROOT.iterdir():
        meta_path = project_dir / "project.json"
        meta = _project_meta(meta_path) if meta_path.exists() else None
        if meta and meta.get("id"):
            ids.add(str(meta["id"]))
    return ids


def recover_legacy_projects() -> dict:
    storage.ensure_data_root()
    found = discover_legacy_projects()
    existing_ids = _existing_project_ids()
    recovered: list[dict] = []
    skipped: list[dict] = []

    for item in found:
        source = Path(item["path"])
        project_id = str(item.get("id") or "")
        if project_id and project_id in existing_ids:
            skipped.append({**item, "reason": "already_present"})
            continue

        base_slug = storage.slugify(str(item.get("slug") or item.get("name") or source.name))
        target_slug = base_slug
        suffix = 2
        while (storage.PROJECTS_ROOT / target_slug).exists():
            target_slug = f"{base_slug}-recovered-{suffix}"
            suffix += 1

        target = storage.PROJECTS_ROOT / target_slug
        try:
            shutil.copytree(source, target)
            meta_path = target / "project.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["slug"] = target_slug
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            shutil.rmtree(target, ignore_errors=True)
            skipped.append({**item, "reason": f"copy_failed: {exc}"})
            continue

        if project_id:
            existing_ids.add(project_id)
        recovered.append(
            {
                **item,
                "source_path": str(source),
                "target_path": str(target),
                "slug": target_slug,
            }
        )

    return {
        "found": len(found),
        "recovered": recovered,
        "recovered_count": len(recovered),
        "skipped": skipped,
        "active_projects_root": str(storage.PROJECTS_ROOT),
        "searched_roots": [str(path) for path in _search_roots()],
    }
