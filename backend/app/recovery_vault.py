"""EmberWriter Recovery Vault: local, versioned, verifiable whole-library backups.

Covers the *entire* local author-data directory (manuscripts, SQLite series,
references, images, audio and settings), not only the Series Vault. Content
addressing reuses identical bytes across generations. A recovery is staged and
verified into a NEW directory, never over an existing manuscript.

No claim that a second folder on the same disk is offsite protection. Authors
must configure a physically independent, encrypted backup drive for that.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from . import storage

LOCK = threading.RLock()
LAST_AUTOMATIC_ERROR: str | None = None
LAST_AUTOMATIC_ATTEMPT: str | None = None
LAST_MIRROR_ERROR: str | None = None
FORMAT = 1
CHUNK = 1024 * 1024
INTERVAL_SECONDS = 15 * 60
ID_PATTERN = re.compile(r"\d{8}T\d{6}Z-[a-f0-9]{12}")
CONFIG_NAME = ".ember-recovery-config.json"
MAX_FILES = 200_000
MAX_TOTAL_BYTES = 500 * 1024**3
MIN_FREE_BYTES = 2 * 1024**3


def _data_root() -> Path:
    return storage.PROJECTS_ROOT.parent.resolve()


def _default_backup_root() -> Path:
    data = _data_root()
    return data.with_name(data.name + "-Recovery").resolve()


def _config_path() -> Path:
    return _data_root() / CONFIG_NAME


def _config() -> dict:
    path = _config_path()
    if not path.exists():
        return {"directory": str(_default_backup_root()), "automatic": True,
                "mirror_directory": None}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Recovery settings are unreadable; refusing unsafe backup") from exc
    if not isinstance(record, dict) or not isinstance(record.get("directory"), str):
        raise TypeError("Invalid recovery settings")
    return {"directory": record["directory"],
            "automatic": record.get("automatic", True) is True,
            "mirror_directory": record.get("mirror_directory") or None}


def _safe_root(location: str) -> Path:
    path = Path(location).expanduser()
    if not path.is_absolute():
        raise ValueError("Backup location must be an absolute path")
    path = path.resolve()
    data = _data_root()
    if path == data or path in data.parents or data in path.parents:
        raise ValueError("Backup destination must be outside the working data directory")
    if path == Path(path.anchor):
        raise ValueError("Choose a dedicated backup folder, not an entire disk root")
    return path


def _backup_root() -> Path:
    return _safe_root(_config()["directory"])


def configure(directory: str, automatic: bool = True,
              mirror_directory: str | None = None) -> dict:
    location = _safe_root(directory)
    mirror = _safe_root(mirror_directory) if mirror_directory else None
    if mirror and (mirror == location or mirror in location.parents or location in mirror.parents):
        raise ValueError("Backup and mirror must be separate folders")
    if location.exists() and not location.is_dir():
        raise ValueError("Backup location must be a directory")
    location.mkdir(parents=True, exist_ok=True)
    marker = location / ".ember-recovery-store"
    if not marker.exists():
        # Never claim an unrelated directory of files as our managed store.
        if any(location.iterdir()):
            raise ValueError("Select a new or empty recovery folder")
        _atomic_bytes(marker, b"EmberWriter Recovery Vault v1\n")
    elif marker.read_bytes() != b"EmberWriter Recovery Vault v1\n":
        raise ValueError("The selected folder is not a valid Recovery Vault")
    if mirror:
        mirror.mkdir(parents=True, exist_ok=True)
        mirror_mark = mirror / ".ember-recovery-store"
        if not mirror_mark.exists():
            if any(mirror.iterdir()):
                raise ValueError("Select a new, empty mirror folder")
            _atomic_bytes(mirror_mark, b"EmberWriter Recovery Vault v1\n")
        elif mirror_mark.read_bytes() != b"EmberWriter Recovery Vault v1\n":
            raise ValueError("Recovery mirror marker is invalid")
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_bytes(path, json.dumps({
        "directory": str(location), "automatic": bool(automatic),
        "mirror_directory": str(mirror) if mirror else None,
    }, indent=2).encode())
    return status()


def _sha(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while data := handle.read(CHUNK):
            digest.update(data)
            total += len(data)
    return digest.hexdigest(), total


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".partial")
    try:
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _object(root: Path, digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Invalid recovery object identifier")
    return root / "objects" / digest[:2] / digest


def _safe_source(path: Path, base: Path) -> None:
    if path.is_symlink() or base not in path.resolve().parents:
        raise ValueError(f"Refusing external link or reparse point in author data: {path}")


def _iter_files(base: Path):
    if not base.exists():
        return
    for directory, folders, filenames in os.walk(base, followlinks=False):
        where = Path(directory)
        _safe_source(where, base.parent)
        folders.sort()
        filenames.sort()
        for name in folders:
            _safe_source(where / name, base)
        for name in filenames:
            file = where / name
            _safe_source(file, base)
            if not file.is_file():
                raise ValueError(f"Unreadable or non-file data item: {file}")
            # These are SQLite runtime sidecars, reconstructed from backed-up
            # transactional databases; ordinary user files are never excluded.
            if name.endswith(("-wal", "-shm")) and file.with_name(name[:-4]).suffix.lower() in {
                ".db", ".sqlite", ".sqlite3",
            }:
                continue
            yield file


def _stage_sqlite(file: Path, temp_dir: Path) -> Path:
    dest = temp_dir / (uuid4().hex + ".db")
    # SQLite's backup API produces a committed, transactionally consistent
    # database even when the live application uses WAL mode.
    source = sqlite3.connect(f"file:{file.as_posix()}?mode=ro", uri=True, timeout=20)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target, pages=256, sleep=0.08)
            check = target.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise ValueError(f"SQLite integrity check failed: {file.name}")
        finally:
            target.close()
    finally:
        source.close()
    return dest


def _store_object(root: Path, file: Path) -> tuple[str, int]:
    digest, size = _sha(file)
    destination = _object(root, digest)
    if destination.is_file():
        existing, existing_size = _sha(destination)
        if existing != digest or existing_size != size:
            raise ValueError("Backup object is corrupted. Do not overwrite it; inspect recovery health.")
        return digest, size
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + "." + uuid4().hex + ".partial")
    try:
        with file.open("rb") as src, temporary.open("xb") as dst:
            shutil.copyfileobj(src, dst, CHUNK)
            dst.flush()
            os.fsync(dst.fileno())
        after, after_size = _sha(temporary)
        if after != digest or after_size != size:
            raise ValueError("Backup bytes changed during copy")
        # Content addresses are never modified once committed.
        if destination.exists():
            known, known_size = _sha(destination)
            if known != digest or known_size != size:
                raise ValueError("Existing recovery object failed integrity checks")
            return digest, size
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return digest, size


def _snapshot_path(root: Path, identifier: str) -> Path:
    if not ID_PATTERN.fullmatch(identifier):
        raise ValueError("Invalid backup generation ID")
    return root / "snapshots" / (identifier + ".json")


def _read_manifest(root: Path, identifier: str) -> dict:
    file = _snapshot_path(root, identifier)
    if not file.is_file():
        raise FileNotFoundError("Recovery generation not found")
    manifest = json.loads(file.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("version") != FORMAT
            or manifest.get("id") != identifier or not isinstance(manifest.get("files"), list)):
        raise ValueError("Recovery manifest is invalid")
    entries = manifest["files"]
    if not isinstance(manifest.get("total_bytes"), int):
        raise TypeError("Recovery manifest has no valid total size")
    if len(entries) > MAX_FILES:
        raise ValueError("Recovery manifest contains too many files")
    paths = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise TypeError("Recovery entry is malformed")
        relative = PurePosixPath(item["path"])
        if ("\\" in item["path"] or ":" in item["path"]
                or relative.is_absolute() or not relative.parts
                or any(part in ("", ".", "..") for part in relative.parts)
                or str(relative) != item["path"]):
            raise ValueError("Recovery entry attempts an unsafe path")
        if item["path"] in paths:
            raise ValueError("Recovery entry is duplicated")
        paths.add(item["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
            raise ValueError("Recovery entry digest is invalid")
        if type(item.get("size")) is not int or item["size"] < 0:
            raise ValueError("Recovery entry size is invalid")
    if sum(item["size"] for item in entries) != manifest["total_bytes"]:
        raise ValueError("Recovery manifest file totals do not match")
    if manifest["total_bytes"] > MAX_TOTAL_BYTES:
        raise ValueError("Recovery generation exceeds the supported storage limit")
    return manifest


def list_generations() -> list[dict]:
    root = _backup_root()
    if not root.exists():
        return []
    summaries = []
    for path in sorted((root / "snapshots").glob("*.json"), reverse=True) if (
        root / "snapshots").exists() else []:
        identifier = path.stem
        if not ID_PATTERN.fullmatch(identifier):
            continue
        try:
            entry = _read_manifest(root, identifier)
            summaries.append({
                "id": identifier, "created_at": entry["created_at"],
                "files": len(entry["files"]), "bytes": entry["total_bytes"],
                "reason": entry.get("reason", "scheduled"),
            })
        except (ValueError, TypeError, OSError, KeyError, json.JSONDecodeError):
            summaries.append({"id": identifier, "invalid_manifest": True})
    return summaries


def status() -> dict:
    config = _config()
    root = _safe_root(config["directory"])
    items = list_generations()
    valid = [item for item in items if not item.get("invalid_manifest")]
    mirror = _safe_root(config["mirror_directory"]) if config["mirror_directory"] else None
    mirror_latest = bool(mirror and valid and _snapshot_path(mirror, valid[0]["id"]).exists())
    return {
        "directory": str(root), "automatic": config["automatic"],
        "snapshot_count": len(valid), "last_snapshot": valid[0] if valid else None,
        "latest_manifest_invalid": bool(items and items[0].get("invalid_manifest")),
        "drive_isolation_verified": False,
        "free_bytes": shutil.disk_usage(root if root.exists() else root.parent).free,
        "mirror_free_bytes": (
            shutil.disk_usage(mirror if mirror.exists() else mirror.parent).free
            if mirror and (mirror.exists() or mirror.parent.exists()) else None
        ),
        "mirror_directory": str(mirror) if mirror else None,
        "mirror_latest_present": mirror_latest,
        "last_mirror_error": LAST_MIRROR_ERROR,
        "last_automatic_error": LAST_AUTOMATIC_ERROR,
        "last_automatic_attempt": LAST_AUTOMATIC_ATTEMPT,
        "warning": ("Backups in a second local folder may be lost with the same disk. "
                    "Select an independent encrypted external drive or replicated location "
                    "and periodically perform a test restore. Snapshots are NOT encrypted "
                    "by EmberWriter; secure the destination with disk encryption."),
    }


def create_backup(reason: str = "manual") -> dict:
    """Never publish a backup manifest until every source object is durable."""
    if not 1 <= len(reason.strip()) <= 120:
        raise ValueError("Give this backup a short reason")
    global LAST_MIRROR_ERROR
    with LOCK:
        root = _backup_root()
        root.mkdir(parents=True, exist_ok=True)
        mark = root / ".ember-recovery-store"
        if mark.exists() and mark.read_bytes() != b"EmberWriter Recovery Vault v1\n":
            raise ValueError("Recovery folder marker is invalid")
        if not mark.exists():
            if any(root.iterdir()):
                raise ValueError("Unrecognized recovery folder, refusing to mix backup data")
            _atomic_bytes(mark, b"EmberWriter Recovery Vault v1\n")
        base = _data_root()
        base.mkdir(parents=True, exist_ok=True)
        items = []
        count = 0
        total = 0
        earlier = next((row for row in list_generations()
                        if not row.get("invalid_manifest")), None)
        previous: dict[str, dict] = {}
        if earlier:
            previous = {
                item["path"]: item for item in _read_manifest(root, earlier["id"])["files"]
            }
        with tempfile.TemporaryDirectory(prefix="ember-sqlite-stage-") as staging:
            temp_dir = Path(staging)
            for file in _iter_files(base):
                relative = file.relative_to(base).as_posix()
                count += 1
                if count > MAX_FILES:
                    raise ValueError("Too many files for one recovery generation")
                is_db = file.suffix.lower() in {".db", ".sqlite", ".sqlite3"}
                before = file.stat()
                cached = previous.get(relative)
                unchanged = (
                    not is_db and cached is not None
                    and cached.get("mtime_ns") == before.st_mtime_ns
                    and cached["size"] == before.st_size
                    and _object(root, cached["sha256"]).is_file()
                    and _object(root, cached["sha256"]).stat().st_size == before.st_size
                )
                if unchanged:
                    digest, size = cached["sha256"], cached["size"]
                elif is_db:
                    staged = _stage_sqlite(file, temp_dir)
                    try:
                        digest, size = _store_object(root, staged)
                    finally:
                        staged.unlink(missing_ok=True)
                else:
                    if shutil.disk_usage(root).free < MIN_FREE_BYTES:
                        raise ValueError(
                            "Recovery storage is low on free space; existing backups "
                            "were preserved and no incomplete generation published.")
                    digest, size = _store_object(root, file)
                after = file.stat()
                if not is_db and (
                    before.st_mtime_ns != after.st_mtime_ns
                    or before.st_size != after.st_size
                ):
                    raise ValueError(
                        "A file changed during backup. No incomplete generation was "
                        "published; retry when author data is stable."
                    )
                total += size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Library exceeds current per-generation backup size limit")
                items.append({"path": relative, "sha256": digest, "size": size,
                              "mtime_ns": before.st_mtime_ns,
                              "sqlite_consistent": is_db})
        identifier = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:12]
        manifest = {"version": FORMAT, "id": identifier,
                    "created_at": datetime.now(UTC).isoformat(),
                    "reason": reason.strip(), "source_root": str(base),
                    "files": items, "total_bytes": total}
        destination = _snapshot_path(root, identifier)
        _atomic_bytes(destination, json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8"))
        mirror_healthy = None
        config = _config()
        if config["mirror_directory"]:
            try:
                _replicate(root, _safe_root(config["mirror_directory"]), identifier)
                mirror_healthy = True
                LAST_MIRROR_ERROR = None
            except (OSError, ValueError) as exc:
                mirror_healthy = False
                LAST_MIRROR_ERROR = f"{type(exc).__name__}: {exc}"
        return {"id": identifier, "created_at": manifest["created_at"],
                "files": count, "bytes": total,
                "verified": True, "destination": str(root),
                "mirror_healthy": mirror_healthy,
                "reason": reason.strip()}


def _replicate(primary: Path, mirror: Path, identifier: str) -> None:
    """Publish a mirror snapshot only after all content objects are durable."""
    if mirror == primary or mirror in primary.parents or primary in mirror.parents:
        raise ValueError("Recovery mirror cannot overlap the primary store")
    mirror.mkdir(parents=True, exist_ok=True)
    marker = mirror / ".ember-recovery-store"
    if not marker.is_file() or marker.read_bytes() != b"EmberWriter Recovery Vault v1\n":
        raise ValueError("Mirror is missing its Recovery Vault marker")
    manifest = _read_manifest(primary, identifier)
    for record in manifest["files"]:
        source = _object(primary, record["sha256"])
        if not source.is_file():
            raise ValueError("Primary object missing during mirror replication")
        digest, size = _store_object(mirror, source)
        if digest != record["sha256"] or size != record["size"]:
            raise ValueError("Mirror object does not match source")
    origin = _snapshot_path(primary, identifier)
    target = _snapshot_path(mirror, identifier)
    if target.exists():
        if target.read_bytes() != origin.read_bytes():
            raise ValueError("Mirrored manifest conflicts with primary generation")
    else:
        _atomic_bytes(target, origin.read_bytes())


def repair_mirror() -> dict:
    global LAST_MIRROR_ERROR
    with LOCK:
        config = _config()
        if not config["mirror_directory"]:
            return {"configured": False, "synced": 0}
        primary = _backup_root()
        mirror = _safe_root(config["mirror_directory"])
        missing = [row["id"] for row in list_generations()
                   if not row.get("invalid_manifest")
                   and not _snapshot_path(mirror, row["id"]).exists()]
        synced = 0
        for identifier in reversed(missing):
            try:
                _replicate(primary, mirror, identifier)
                synced += 1
                LAST_MIRROR_ERROR = None
            except (ValueError, OSError) as exc:
                LAST_MIRROR_ERROR = f"{type(exc).__name__}: {exc}"
                break
        return {"configured": True, "synced": synced,
                "remaining": len(missing) - synced, "error": LAST_MIRROR_ERROR}


def verify(identifier: str) -> dict:
    with LOCK:
        root = _backup_root()
        manifest = _read_manifest(root, identifier)
        checked = 0
        bad = []
        for record in manifest["files"]:
            destination = _object(root, record["sha256"])
            if not destination.is_file():
                bad.append({"path": record["path"], "problem": "missing_object"})
                continue
            digest, size = _sha(destination)
            if digest != record["sha256"] or size != record["size"]:
                bad.append({"path": record["path"], "problem": "checksum_mismatch"})
            else:
                checked += 1
        return {"id": identifier, "healthy": not bad,
                "checked_files": checked, "bad": bad[:100],
                "total_files": len(manifest["files"]),
                "status": "verified" if not bad else "damaged"}


def verify_paths(identifier: str, protected_paths: list[str] | None = None) -> dict:
    """Verify the exact material about to be deleted; full verification remains available."""
    with LOCK:
        root = _backup_root()
        manifest = _read_manifest(root, identifier)
        allowed = protected_paths or []
        items = [item for item in manifest["files"]
                 if not allowed or any(
                     item["path"] == requested.rstrip("/")
                     or item["path"].startswith(requested.rstrip("/") + "/")
                     for requested in allowed
                 )]
        if allowed and not items:
            raise ValueError("Backup contains none of the material to be deleted")
        bad = []
        for row in items:
            path = _object(root, row["sha256"])
            if not path.is_file():
                bad.append(row["path"])
                continue
            sha, size = _sha(path)
            if sha != row["sha256"] or size != row["size"]:
                bad.append(row["path"])
        return {"healthy": not bad, "checked_files": len(items),
                "corrupted_files": bad[:100]}


def preview_restore(identifier: str) -> dict:
    root = _backup_root()
    record = _read_manifest(root, identifier)
    return {
        "id": identifier, "created_at": record["created_at"],
        "total_files": len(record["files"]),
        "bytes": record["total_bytes"],
        "projects": sorted({p["path"].split("/")[1] for p in record["files"]
                            if p["path"].startswith("projects/")
                            and len(p["path"].split("/")) >= 3}),
        "has_series": any(p["path"].startswith("series/") for p in record["files"]),
        "includes_media": any(
            p["path"].lower().endswith((".png", ".jpg", ".jpeg", ".webp",
                                       ".wav", ".mp3", ".flac", ".m4b", ".mp4"))
            for p in record["files"]),
        "files": [{"path": p["path"], "bytes": p["size"]} for p in record["files"][:75]],
        "warning": "Restore always creates a separate new library; the current one is never replaced.",
    }


def restore(identifier: str, *, destination: str | None = None) -> dict:
    """Verify all hashes, restore into a new sibling directory, then publish atomically."""
    with LOCK:
        healthy = verify(identifier)
        if not healthy["healthy"]:
            raise ValueError("Recovery generation is damaged; no files were restored")
        root = _backup_root()
        manifest = _read_manifest(root, identifier)
        data = _data_root()
        base = Path(destination).expanduser().resolve() if destination else (
            data.parent / "EmberWriter-Recovered" / identifier).resolve()
        if (base == data or base in data.parents or data in base.parents
                or base == root or base in root.parents or root in base.parents):
            raise ValueError("Recovery destination must not overlap live data or backup store")
        if base.exists():
            raise FileExistsError("Recovery destination already exists; refusing to overwrite")
        base.parent.mkdir(parents=True, exist_ok=True)
        staging = base.with_name(base.name + "." + uuid4().hex + ".restoring")
        staging.mkdir(mode=0o700)
        try:
            for record in manifest["files"]:
                relative = PurePosixPath(record["path"])
                out = staging.joinpath(*relative.parts)
                if staging not in out.resolve().parents:
                    raise ValueError("Unsafe recovery destination path")
                out.parent.mkdir(parents=True, exist_ok=True)
                source = _object(root, record["sha256"])
                with source.open("rb") as inp, out.open("xb") as dest:
                    shutil.copyfileobj(inp, dest, CHUNK)
                    dest.flush()
                    os.fsync(dest.fileno())
                check, length = _sha(out)
                if check != record["sha256"] or length != record["size"]:
                    raise ValueError("Restore verification failed; no new library published")
            os.replace(staging, base)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return {"restored": True, "generation_id": identifier,
                "directory": str(base), "files": len(manifest["files"]),
                "current_library_changed": False,
                "next_step": ("Inspect the recovered library. Start EmberWriter pointing "
                              "its -DataDir option at this directory to use it as a separate library.")}


def backup_due() -> bool:
    if not _config()["automatic"]:
        return False
    records = list_generations()
    valid = next((r for r in records if not r.get("invalid_manifest")), None)
    if valid is None:
        return True
    age = datetime.now(UTC) - datetime.fromisoformat(valid["created_at"])
    return age.total_seconds() >= INTERVAL_SECONDS


def backup_if_due() -> dict | None:
    global LAST_AUTOMATIC_ERROR, LAST_AUTOMATIC_ATTEMPT
    if not _config()["automatic"]:
        return None
    repair_mirror()
    if not backup_due():
        return None
    LAST_AUTOMATIC_ATTEMPT = datetime.now(UTC).isoformat()
    try:
        result = create_backup("automatic")
        LAST_AUTOMATIC_ERROR = None
        return result
    except (ValueError, OSError, sqlite3.Error) as exc:
        LAST_AUTOMATIC_ERROR = f"{type(exc).__name__}: {exc}"
        raise


def before_destructive_action(action: str, protected_paths: list[str] | None = None) -> dict:
    """Fail closed: do not delete original writing unless a verified backup exists."""
    result = create_backup("before " + action[:90])
    report = verify_paths(result["id"], protected_paths)
    if not report["healthy"] or result["mirror_healthy"] is False:
        raise ValueError("Pre-delete backup or configured mirror failed verification. Original work was preserved.")
    return result
