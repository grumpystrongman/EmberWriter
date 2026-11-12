from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from .board import (
    BOARD_ASSET_LIMIT,
    board_asset_path,
    create_item,
    delete_item,
    load_board,
    store_asset,
    update_item,
)
from .board_models import BoardItem, BoardItemCreate, BoardItemUpdate, BoardState
from .routes_visual_interpret import ImageInterpretRequest, describe_reference_image

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
    parent_note_id: Annotated[str, Form(max_length=200)] = "",
) -> BoardItem:
    try:
        data = await file.read(BOARD_ASSET_LIMIT + 1)
        return store_asset(
            slug,
            filename=file.filename or "attachment",
            content=data,
            content_type=file.content_type or "application/octet-stream",
            x=x,
            y=y,
            parent_note_id=parent_note_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/board/asset")
def get_asset(slug: str, path: Annotated[str, Query(min_length=1)]) -> FileResponse:
    try:
        asset = board_asset_path(slug, path)
        if asset.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}:
            return FileResponse(asset, headers={"X-Content-Type-Options": "nosniff"})
        return FileResponse(asset, media_type="application/octet-stream", filename=asset.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Board asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/board/items/{item_id}/describe")
async def describe_attachment(slug: str, item_id: str, payload: ImageInterpretRequest) -> dict:
    try:
        image = next((item for item in load_board(slug).items
                      if item.id == item_id and item.kind == "image" and item.parent_note_id), None)
        if image is None:
            raise FileNotFoundError(item_id)
        path = board_asset_path(slug, image.asset_path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Note image not found") from exc
    return {"description": await describe_reference_image(path, payload)}
