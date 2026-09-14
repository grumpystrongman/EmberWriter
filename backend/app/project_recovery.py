from __future__ import annotations

import json
import os
import shutil
import string
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

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
    "appdata",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "$recycle.bin",
    "system volume information",
    "recovery",
    "perflogs",
    "msocache",
}
_PROJECT_SIGNAL_DIRS = {
    "characters",
    "world",
    "relationships",
    "timeline",
    "scenes",
    "style",
    "summaries",
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
    project_dir = path.parent
    if not (project_dir / "manuscript").exists() and not (project_dir / ".ember" / "story.db").exists():
        return None
    return payload


def _windows_drive_roots() -> list[Path]:
    if os.name != "nt":
        return []
    roots: list[Path] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        try:
            if root.exists() and root.is_dir():
                roots.append(root)
        except OSError:
            continue
    return roots


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

    # The previous recovery pass only searched the user's normal profile folders.
    # Old clones are often on C:\, D:\, or another development drive, so include
    # every mounted Windows drive as a final fallback. System/package folders are
    # aggressively pruned during the walk below.
    candidates.extend(_windows_drive_roots())

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


def _legacy_signature(project_dir: Path) -> bool:
    manuscript = project_dir / "manuscript"
    story_db = project_dir / ".ember" / "story.db"
    if story_db.exists() and manuscript.exists():
        return True
    if not manuscript.exists() or not manuscript.is_dir():
        return False
    signal_count = sum((project_dir / name).exists() for name in _PROJECT_SIGNAL_DIRS)
    if signal_count < 2:
        return False
    try:
        return any(
            path.is_file() and path.suffix.lower() in {".md", ".txt"}
            for path in manuscript.rglob("*")
        )
    except OSError:
        return False


def _candidate_project(project_dir: Path) -> dict | None:
    meta_path = project_dir / "project.json"
    meta = _project_meta(meta_path) if meta_path.exists() else None
    if meta is not None:
        return {
            "path": str(project_dir),
            "name": meta.get("name", project_dir.name),
            "slug": meta.get("slug", project_dir.name),
            "id": meta.get("id", ""),
            "updated_at": meta.get("updated_at", meta.get("created_at", "")),
            "signature": "project_json",
        }

    if not _legacy_signature(project_dir):
        return None
    try:
        updated = datetime.fromtimestamp(project_dir.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        updated = ""
    return {
        "path": str(project_dir),
        "name": project_dir.name.replace("-", " ").replace("_", " ").strip() or "Recovered project",
        "slug": storage.slugify(project_dir.name),
        "id": "",
        "updated_at": updated,
        "signature": "legacy_structure",
    }


def discover_legacy_projects(max_results: int = 250, max_depth: int = 12) -> list[dict]:
    active_root = storage.PROJECTS_ROOT.resolve()
    discovered: list[dict] = []
    seen_dirs: set[Path] = set()

    for search_root in _search_roots():
        root_depth = len(search_root.parts)

        def ignore_walk_error(_: OSError) -> None:
            return None

        for dirpath, dirnames, filenames in os.walk(
            search_root,
            topdown=True,
            followlinks=False,
            onerror=ignore_walk_error,
        ):
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
                dirnames[:] = [
                    name for name in dirnames if name.casefold() not in _SKIP_DIR_NAMES
                ]

            if resolved == active_root or active_root in resolved.parents:
                dirnames[:] = []
                continue
            if resolved in seen_dirs:
                continue

            likely_candidate = (
                "project.json" in filenames
                or "manuscript" in dirnames
                or ".ember" in dirnames
            )
            if not likely_candidate:
                continue

            item = _candidate_project(resolved)
            if item is None:
                continue
            seen_dirs.add(resolved)
            discovered.append(item)
            if len(discovered) >= max_results:
                return discovered
    return discovered


def _existing_project_keys() -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    sources: set[str] = set()
    if not storage.PROJECTS_ROOT.exists():
        return ids, sources
    for project_dir in storage.PROJECTS_ROOT.iterdir():
        meta_path = project_dir / "project.json"
        meta = _project_meta(meta_path) if meta_path.exists() else None
        if not meta:
            continue
        if meta.get("id"):
            ids.add(str(meta["id"]))
        if meta.get("recovered_from"):
            try:
                sources.add(str(Path(str(meta["recovered_from"])).resolve()).casefold())
            except OSError:
                sources.add(str(meta["recovered_from"]).casefold())
    return ids, sources


def _metadata_for_recovery(item: dict, target_slug: str, source: Path) -> dict:
    source_meta_path = source / "project.json"
    source_meta = _project_meta(source_meta_path) if source_meta_path.exists() else None
    if source_meta is not None:
        meta = dict(source_meta)
    else:
        now = item.get("updated_at") or datetime.now(UTC).isoformat()
        meta = {
            "schema_version": 1,
            "id": str(uuid4()),
            "name": item.get("name") or source.name,
            "description": "Recovered from an earlier EmberWriter project folder.",
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
    meta["slug"] = target_slug
    meta["recovered_from"] = str(source)
    return meta


def recover_legacy_projects() -> dict:
    storage.ensure_data_root()
    found = discover_legacy_projects()
    existing_ids, existing_sources = _existing_project_keys()
    recovered: list[dict] = []
    skipped: list[dict] = []

    for item in found:
        source = Path(item["path"])
        try:
            source_key = str(source.resolve()).casefold()
        except OSError:
            source_key = str(source).casefold()
        project_id = str(item.get("id") or "")
        if project_id and project_id in existing_ids:
            skipped.append({**item, "reason": "already_present"})
            continue
        if source_key in existing_sources:
            skipped.append({**item, "reason": "already_recovered_from_source"})
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
            meta = _metadata_for_recovery(item, target_slug, source)
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            shutil.rmtree(target, ignore_errors=True)
            skipped.append({**item, "reason": f"copy_failed: {exc}"})
            continue

        recovered_id = str(meta.get("id") or "")
        if recovered_id:
            existing_ids.add(recovered_id)
        existing_sources.add(source_key)
        recovered.append(
            {
                **item,
                "source_path": str(source),
                "target_path": str(target),
                "slug": target_slug,
            }
        )

    searched_roots = [str(path) for path in _search_roots()]
    return {
        "attempted": True,
        "found": len(found),
        "recovered": recovered,
        "recovered_count": len(recovered),
        "skipped": skipped,
        "active_projects_root": str(storage.PROJECTS_ROOT),
        "searched_roots": searched_roots,
        "drive_wide_scan": any(Path(root).anchor == root for root in searched_roots),
    }
