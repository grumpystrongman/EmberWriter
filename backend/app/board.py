from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import uuid4

from .board_models import BoardItem, BoardItemCreate, BoardItemUpdate, BoardState
from .storage import project_root, utc_now

BOARD_ASSET_LIMIT = 50 * 1024 * 1024


def _ensure_project(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root


def _board_path(slug: str) -> Path:
    return _ensure_project(slug) / "planning" / "corkboard.json"


def _safe_board_asset_path(slug: str, relative_path: str) -> Path:
    root = _ensure_project(slug)
    asset_root = (root / "assets" / "board").resolve()
    candidate = (root / relative_path).resolve()
    if candidate == asset_root or asset_root not in candidate.parents:
        raise ValueError("Only project Corkboard assets can be accessed")
    return candidate


def load_board(slug: str) -> BoardState:
    path = _board_path(slug)
    if not path.exists():
        return BoardState()
    return BoardState.model_validate_json(path.read_text(encoding="utf-8"))


def save_board(slug: str, state: BoardState) -> BoardState:
    path = _board_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(state.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return state


def create_item(slug: str, payload: BoardItemCreate) -> BoardItem:
    state = load_board(slug)
    now = utc_now()
    top_z = max((item.z for item in state.items), default=0) + 1
    item = BoardItem(
        id=uuid4().hex,
        kind=payload.kind,
        title=payload.title.strip(),
        body=payload.body,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        z=top_z,
        color=payload.color,
        url=payload.url.strip(),
        binder_node_id=payload.binder_node_id.strip(),
        created_at=now,
        updated_at=now,
    )
    state.items.append(item)
    save_board(slug, state)
    return item


def update_item(slug: str, item_id: str, payload: BoardItemUpdate) -> BoardItem:
    state = load_board(slug)
    for index, item in enumerate(state.items):
        if item.id != item_id:
            continue
        updates = payload.model_dump(exclude_none=True)
        updates["updated_at"] = utc_now()
        updated = item.model_copy(update=updates)
        state.items[index] = updated
        save_board(slug, state)
        return updated
    raise FileNotFoundError(item_id)


def delete_item(slug: str, item_id: str) -> None:
    state = load_board(slug)
    if not any(item.id == item_id for item in state.items):
        raise FileNotFoundError(item_id)
    state.items = [item for item in state.items if item.id != item_id]
    save_board(slug, state)
    # Uploaded board assets intentionally remain in the project. Whole-project checkpoints
    # currently snapshot the board JSON but do not duplicate binary files. Keeping the asset
    # makes a later project-history restore able to recover a removed image/file reference.


def _safe_filename(filename: str) -> str:
    base = Path(filename).name.strip() or "attachment"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(base).stem).strip("-.") or "attachment"
    suffix = re.sub(r"[^A-Za-z0-9.]", "", Path(base).suffix.lower())[:16]
    return f"{stem[:120]}{suffix}"


def store_asset(
    slug: str,
    *,
    filename: str,
    content: bytes,
    content_type: str,
    x: float = 100,
    y: float = 100,
) -> BoardItem:
    _ensure_project(slug)
    if not content:
        raise ValueError("Uploaded board asset is empty")
    if len(content) > BOARD_ASSET_LIMIT:
        raise ValueError("Board asset exceeds the 50 MB project limit")
    safe_name = _safe_filename(filename)
    asset_id = uuid4().hex
    relative = f"assets/board/{asset_id}-{safe_name}"
    target = _safe_board_asset_path(slug, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    kind = "image" if content_type.startswith("image/") else "attachment"
    now = utc_now()
    state = load_board(slug)
    item = BoardItem(
        id=uuid4().hex,
        kind=kind,
        title=Path(filename).name,
        body="",
        x=x,
        y=y,
        width=320 if kind == "image" else 300,
        height=240 if kind == "image" else 150,
        z=max((entry.z for entry in state.items), default=0) + 1,
        color="slate",
        asset_path=relative,
        original_filename=Path(filename).name,
        created_at=now,
        updated_at=now,
    )
    state.items.append(item)
    save_board(slug, state)
    return item


def board_asset_path(slug: str, relative_path: str) -> Path:
    path = _safe_board_asset_path(slug, relative_path)
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return path
