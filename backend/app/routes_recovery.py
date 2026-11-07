"""Recovery Center API: local-only full-library backup, verification and safe restore."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import recovery_vault as vault

router = APIRouter(prefix="/api/recovery", tags=["Author Recovery"])


class RecoveryConfig(BaseModel):
    directory: str = Field(min_length=3, max_length=2000)
    automatic: bool = True


class BackupRequest(BaseModel):
    reason: str = Field(default="author initiated", min_length=1, max_length=120)


class RestoreRequest(BaseModel):
    # Deliberately do not let the UI replace any existing working library.
    destination: str | None = Field(default=None, max_length=2000)
    confirmed: bool = False


def _error(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, "Backup generation not found") from exc
    if isinstance(exc, FileExistsError):
        raise HTTPException(409, "Recovery folder exists. Choose a new empty location.") from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("/status")
def status() -> dict:
    try:
        return vault.status()
    except (OSError, ValueError) as exc:
        _error(exc)


@router.post("/settings")
def settings(payload: RecoveryConfig) -> dict:
    try:
        return vault.configure(payload.directory, payload.automatic)
    except (OSError, ValueError) as exc:
        _error(exc)


@router.get("/generations")
def generations() -> list[dict]:
    try:
        return vault.list_generations()
    except (OSError, ValueError) as exc:
        _error(exc)


@router.post("/backup", status_code=201)
async def create(payload: BackupRequest) -> dict:
    try:
        return await asyncio.to_thread(vault.create_backup, payload.reason)
    except (OSError, ValueError) as exc:
        _error(exc)


@router.get("/generations/{identifier}")
def preview(identifier: str) -> dict:
    try:
        return vault.preview_restore(identifier)
    except (OSError, ValueError) as exc:
        _error(exc)


@router.post("/generations/{identifier}/verify")
async def verify(identifier: str) -> dict:
    try:
        return await asyncio.to_thread(vault.verify, identifier)
    except (OSError, ValueError) as exc:
        _error(exc)


@router.post("/generations/{identifier}/restore", status_code=201)
async def restore(identifier: str, payload: RestoreRequest) -> dict:
    if not payload.confirmed:
        raise HTTPException(400, "Confirm that you want an independent recovered copy")
    try:
        return await asyncio.to_thread(
            vault.restore, identifier, destination=payload.destination)
    except (OSError, ValueError, FileExistsError) as exc:
        _error(exc)


async def automatic_recovery_loop() -> None:
    """Never block the editor for backups; retry errors without deleting older copies."""
    await asyncio.sleep(7)
    while True:
        try:
            await asyncio.to_thread(vault.backup_if_due)
        except (OSError, ValueError):
            # Status errors remain visible from the Recovery Center. Previous
            # verified snapshots are retained; no pruning on failure.
            pass
        await asyncio.sleep(60)
