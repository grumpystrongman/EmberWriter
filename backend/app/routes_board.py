from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from .board import (
    board_asset_path,
    create_item,
    delete_item,
    load_board,
    store_asset,
    update_item,
)
from .board_models import BoardItem, BoardItemCreate, BoardItemUpdate, BoardState

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/board", response_model=BoardState)
def get_board(slug: str) -> BoardState:
    try:
        return load_board(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/board/items", response_model=BoardItem)
def post_item(slug: str, payload: BoardItemCreate) -> BoardItem:
    try:
        return create_item(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/projects/{slug}/board/items/{item_id}", response_model=BoardItem)
def patch_item(slug: str, item_id: str, payload: BoardItemUpdate) -> BoardItem:
    try:
        return update_item(slug, item_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Board item not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{slug}/board/items/{item_id}")
def remove_item(slug: str, item_id: str) -> dict:
    try:
        delete_item(slug, item_id)
        return {"deleted": item_id}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Board item not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/board/upload", response_model=BoardItem)
async def upload_item(
    slug: str,
    file: Annotated[UploadFile, File(...)],
    x: Annotated[float, Form()] = 100,
    y: Annotated[float, Form()] = 100,
) -> BoardItem:
    try:
        data = await file.read()
        return store_asset(
            slug,
            filename=file.filename or "attachment",
            content=data,
            content_type=file.content_type or "application/octet-stream",
            x=x,
            y=y,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/board/asset")
def get_asset(slug: str, path: Annotated[str, Query(min_length=1)]) -> FileResponse:
    try:
        return FileResponse(board_asset_path(slug, path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Board asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
