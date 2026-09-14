from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
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
_LOCATION_COMMAND = re.compile(
    r"^\s*(?:cd|chdir|sl|set-location|pushd)\s+(?:-literalpath\s+|-path\s+)?(.+?)\s*$",
    re.IGNORECASE,
)


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
    if not _project_has_recoverable_content(project_dir):
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


def _clean_history_path(raw: str) -> str:
    value = raw.strip()
    if value.startswith("--%"):
        value = value[3:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    value = os.path.expandvars(os.path.expanduser(value.strip()))
    return value


def _history_location_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = _LOCATION_COMMAND.match(line)
        if not match:
            continue
        value = _clean_history_path(match.group(1))
        if not value or value.startswith("-"):
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(value)
    return candidates


def _powershell_history_roots() -> list[Path]:
    if os.name != "nt":
        return []
    home = Path.home()
    appdata = os.getenv("APPDATA")
    bases = [Path(appdata)] if appdata else [home / "AppData" / "Roaming"]
    history_files: list[Path] = []
    for base in bases:
        history_files.extend(
            [
                base / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
                base / "Microsoft" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
            ]
        )

    roots: list[Path] = []
    for history_file in history_files:
        try:
            text = history_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for value in _history_location_candidates(text):
            try:
                path = Path(value).expanduser()
                if path.is_absolute() and path.exists() and path.is_dir():
                    roots.append(path)
            except OSError:
                continue
    return roots


def _historical_windows_launch_roots() -> list[Path]:
    """Locations the pre-2026-09-14 launcher could have inherited as CWD.

    Before commit 20b961d, start.ps1 did not set WorkingDirectory and storage.py
    resolved the relative data directory from the inherited process CWD. These
    roots are therefore evidence-driven recovery locations, not generic guesses.
    """
    if os.name != "nt":
        return []

    home = Path.home()
    windir = Path(os.getenv("WINDIR", r"C:\Windows"))
    program_files = Path(os.getenv("ProgramFiles", r"C:\Program Files"))
    candidates: list[Path] = [
        windir / "System32",
        windir / "SysWOW64",
        windir / "System32" / "WindowsPowerShell" / "v1.0",
        program_files / "PowerShell" / "7",
        program_files / "PowerShell" / "6",
        home,
    ]

    for variable in ("USERPROFILE", "PUBLIC", "TEMP", "TMP"):
        value = os.getenv(variable)
        if value:
            candidates.append(Path(value))

    candidates.extend(_powershell_history_roots())

    # A deleted old clone or data tree may still be recoverable from the current
    # user's Recycle Bin. Probe each drive's recycle root explicitly before the
    # broader drive walk, which intentionally prunes $Recycle.Bin.
    for drive in _windows_drive_roots():
        candidates.append(drive / "$Recycle.Bin")

    return candidates


def _search_roots() -> list[Path]:
    candidates: list[Path] = []
    home = Path.home()
    repo_root = Path(__file__).resolve().parents[2]
    current = Path.cwd().resolve()

    env_roots = os.getenv("EMBER_RECOVERY_ROOTS", "")
    if env_roots:
        candidates.extend(
            Path(item).expanduser() for item in env_roots.split(os.pathsep) if item
        )

    # Search historically plausible launcher roots first. Several are nested
    # beneath directories that the generic profile/drive scan prunes, so order
    # matters: explicit evidence roots must be walked before their parents.
    candidates.extend(_historical_windows_launch_roots())

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
            repo_root,
            repo_root / "backend",
            repo_root.parent,
            current,
            current.parent,
        ]
    )

    one_drive = os.getenv("OneDrive") or os.getenv("ONEDRIVE")
    if one_drive:
        candidates.append(Path(one_drive))

    # Old clones are often on C:\, D:\, or another development drive. Include
    # every mounted Windows drive as a final fallback and prune system/package
    # folders aggressively while walking them. Explicit historical roots above
    # cover the system locations that must not be pruned for this forensic pass.
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


def _snapshot_files(project_dir: Path) -> list[Path]:
    snapshots = project_dir / ".ember" / "snapshots"
    if not snapshots.exists():
        return []
    try:
        return [
            path
            for path in snapshots.rglob("*")
            if path.is_file() and "manuscript" in path.parts and path.suffix.lower() in {".md", ".txt"}
        ]
    except OSError:
        return []


def _db_has_recoverable_content(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
            tables = {
                row[0]
                for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if "document_revisions" in tables:
                row = con.execute(
                    "SELECT 1 FROM document_revisions WHERE path LIKE 'manuscript/%' AND length(content) > 0 LIMIT 1"
                ).fetchone()
                if row:
                    return True
            if "project_checkpoint_files" in tables:
                row = con.execute(
                    "SELECT 1 FROM project_checkpoint_files WHERE path LIKE 'manuscript/%' AND length(content) > 0 LIMIT 1"
                ).fetchone()
                if row:
                    return True
    except sqlite3.Error:
        return False
    return False


def _project_has_recoverable_content(project_dir: Path) -> bool:
    manuscript = project_dir / "manuscript"
    if manuscript.exists() and manuscript.is_dir():
        try:
            if any(
                path.is_file() and path.suffix.lower() in {".md", ".txt"}
                for path in manuscript.rglob("*")
            ):
                return True
        except OSError:
            pass
    if _snapshot_files(project_dir):
        return True
    return _db_has_recoverable_content(project_dir / ".ember" / "story.db")


def _legacy_signature(project_dir: Path) -> bool:
    if _project_has_recoverable_content(project_dir):
        return True
    manuscript = project_dir / "manuscript"
    if not manuscript.exists() or not manuscript.is_dir():
        return False
    signal_count = sum((project_dir / name).exists() for name in _PROJECT_SIGNAL_DIRS)
    return signal_count >= 2


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
    recovered_name = project_dir.name.replace("-", " ").replace("_", " ").strip()
    signature = "history_only" if not (project_dir / "manuscript").exists() else "legacy_structure"
    return {
        "path": str(project_dir),
        "name": recovered_name or "Recovered project",
        "slug": storage.slugify(project_dir.name),
        "id": "",
        "updated_at": updated,
        "signature": signature,
    }


def _direct_historical_projects() -> list[dict]:
    """Probe the exact relative path used by storage.py before CWD was fixed."""
    discovered: list[dict] = []
    seen: set[Path] = set()
    roots = _historical_windows_launch_roots() + [Path.home(), Path.cwd()]
    for cwd in roots:
        for projects_dir in (cwd / "data" / "projects", cwd / "backend" / "data" / "projects"):
            try:
                if not projects_dir.exists() or not projects_dir.is_dir():
                    continue
                for project_dir in projects_dir.iterdir():
                    if not project_dir.is_dir():
                        continue
                    resolved = project_dir.resolve()
                    if resolved in seen or resolved == storage.PROJECTS_ROOT.resolve():
                        continue
                    item = _candidate_project(resolved)
                    if item:
                        item["discovery"] = "historical_cwd_data_root"
                        discovered.append(item)
                        seen.add(resolved)
            except OSError:
                continue
    return discovered


def discover_legacy_projects(max_results: int = 250, max_depth: int = 12) -> list[dict]:
    active_root = storage.PROJECTS_ROOT.resolve()
    discovered = _direct_historical_projects()
    seen_dirs: set[Path] = set()
    for item in discovered:
        try:
            seen_dirs.add(Path(item["path"]).resolve())
        except OSError:
            continue
    completed_roots: list[Path] = []

    if len(discovered) >= max_results:
        return discovered[:max_results]

    for search_root in _search_roots():
        try:
            resolved_search_root = search_root.resolve()
        except OSError:
            continue
        if any(
            resolved_search_root == prior or prior in resolved_search_root.parents
            for prior in completed_roots
        ):
            continue
        root_depth = len(resolved_search_root.parts)

        def ignore_walk_error(_: OSError) -> None:
            return None

        for dirpath, dirnames, filenames in os.walk(
            resolved_search_root,
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

            if any(
                resolved == prior or prior in resolved.parents for prior in completed_roots
            ):
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
            item.setdefault("discovery", "filesystem_signature")
            seen_dirs.add(resolved)
            discovered.append(item)
            if len(discovered) >= max_results:
                return discovered

        completed_roots.append(resolved_search_root)
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
                sources.add(
                    str(Path(str(meta["recovered_from"])).resolve()).casefold()
                )
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


def _history_versions(project_dir: Path) -> dict[str, tuple[str, str, str]]:
    """Return newest recoverable manuscript content by path.

    Values are (sort_key, content, source). Existing manuscript files are not
    included because recovery never overwrites live author text.
    """
    versions: dict[str, tuple[str, str, str]] = {}
    db_path = project_dir / ".ember" / "story.db"
    if db_path.exists():
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
                tables = {
                    row[0]
                    for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                if "document_revisions" in tables:
                    rows = con.execute(
                        "SELECT path, created_at, content FROM document_revisions "
                        "WHERE path LIKE 'manuscript/%' AND length(content) > 0 "
                        "ORDER BY created_at DESC"
                    ).fetchall()
                    for path, created_at, content in rows:
                        if path not in versions:
                            versions[path] = (str(created_at), str(content), "story_db_revision")
                if {"project_checkpoints", "project_checkpoint_files"}.issubset(tables):
                    rows = con.execute(
                        "SELECT f.path, c.created_at, f.content "
                        "FROM project_checkpoint_files f "
                        "JOIN project_checkpoints c ON c.id = f.checkpoint_id "
                        "WHERE f.path LIKE 'manuscript/%' AND length(f.content) > 0 "
                        "ORDER BY c.created_at DESC"
                    ).fetchall()
                    for path, created_at, content in rows:
                        existing = versions.get(path)
                        candidate = (str(created_at), str(content), "project_checkpoint")
                        if existing is None or candidate[0] > existing[0]:
                            versions[path] = candidate
        except sqlite3.Error:
            pass

    snapshots = project_dir / ".ember" / "snapshots"
    if snapshots.exists():
        try:
            for snapshot in snapshots.rglob("*"):
                if not snapshot.is_file() or snapshot.suffix.lower() not in {".md", ".txt"}:
                    continue
                try:
                    relative = snapshot.relative_to(snapshots)
                except ValueError:
                    continue
                parts = relative.parts
                if len(parts) < 3 or parts[1] != "manuscript":
                    continue
                story_path = Path(*parts[1:]).as_posix()
                sort_key = parts[0]
                try:
                    content = snapshot.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    continue
                existing = versions.get(story_path)
                candidate = (sort_key, content, "snapshot")
                if content and (existing is None or candidate[0] > existing[0]):
                    versions[story_path] = candidate
        except OSError:
            pass
    return versions


def _restore_missing_manuscript_from_history(project_dir: Path) -> list[dict]:
    restored: list[dict] = []
    for relative, (_, content, source) in _history_versions(project_dir).items():
        destination = project_dir / Path(relative)
        try:
            if destination.exists() and destination.is_file() and destination.stat().st_size > 0:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            restored.append({"path": relative, "source": source, "words": len(content.split())})
        except (OSError, UnicodeError):
            continue
    return restored


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

        base_slug = storage.slugify(
            str(item.get("slug") or item.get("name") or source.name)
        )
        target_slug = base_slug
        suffix = 2
        while (storage.PROJECTS_ROOT / target_slug).exists():
            target_slug = f"{base_slug}-recovered-{suffix}"
            suffix += 1

        target = storage.PROJECTS_ROOT / target_slug
        try:
            shutil.copytree(source, target)
            restored_history = _restore_missing_manuscript_from_history(target)
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
                "history_restored": restored_history,
                "history_restored_count": len(restored_history),
            }
        )

    searched_roots = [str(path) for path in _search_roots()]
    return {
        "attempted": True,
        "found": len(found),
        "recovered": recovered,
        "recovered_count": len(recovered),
        "history_restored_count": sum(item.get("history_restored_count", 0) for item in recovered),
        "skipped": skipped,
        "active_projects_root": str(storage.PROJECTS_ROOT),
        "searched_roots": searched_roots,
        "historical_launch_roots": [str(path) for path in _historical_windows_launch_roots()],
        "drive_wide_scan": any(Path(root).anchor == root for root in searched_roots),
    }
