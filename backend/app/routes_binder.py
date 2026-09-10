from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .binder import (
    create_collection,
    create_node,
    get_binder,
    reorder_nodes,
    restore_node,
    sync_binder,
    trash_node,
    update_collection,
    update_node,
)
from .binder_models import (
    BinderCollectionCreate,
    BinderCollectionUpdate,
    BinderNodeCreate,
    BinderNodeUpdate,
    BinderReorderRequest,
    BinderState,
)

router = APIRouter(prefix="/api")


def _not_found(exc: FileNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc) or "Binder resource not found")


def _owned(slug: str, state: BinderState) -> BinderState:
    return state.model_copy(update={"project_slug": slug})


@router.get("/projects/{slug}/binder", response_model=BinderState)
def binder(slug: str) -> BinderState:
    try:
        return _owned(slug, get_binder(slug))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/sync", response_model=BinderState)
def sync(slug: str) -> BinderState:
    try:
        return _owned(slug, sync_binder(slug))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/nodes", response_model=BinderState)
def new_node(slug: str, payload: BinderNodeCreate) -> BinderState:
    try:
        return _owned(slug, create_node(slug, payload))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{slug}/binder/nodes/{node_id}", response_model=BinderState)
def edit_node(slug: str, node_id: str, payload: BinderNodeUpdate) -> BinderState:
    try:
        return _owned(slug, update_node(slug, node_id, payload))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/reorder", response_model=BinderState)
def reorder(slug: str, payload: BinderReorderRequest) -> BinderState:
    try:
        return _owned(slug, reorder_nodes(slug, payload))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/nodes/{node_id}/trash", response_model=BinderState)
def trash(slug: str, node_id: str) -> BinderState:
    try:
        return _owned(slug, trash_node(slug, node_id))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/nodes/{node_id}/restore", response_model=BinderState)
def restore(slug: str, node_id: str) -> BinderState:
    try:
        return _owned(slug, restore_node(slug, node_id))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/binder/collections", response_model=BinderState)
def new_collection(slug: str, payload: BinderCollectionCreate) -> BinderState:
    try:
        return _owned(slug, create_collection(slug, payload))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/projects/{slug}/binder/collections/{collection_id}",
    response_model=BinderState,
)
def edit_collection(
    slug: str,
    collection_id: str,
    payload: BinderCollectionUpdate,
) -> BinderState:
    try:
        return _owned(slug, update_collection(slug, collection_id, payload))
    except FileNotFoundError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
