from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from .media_models import CharacterPortraitGenerateRequest, CharacterPortraitResponse
from .storage import project_root, slugify, utc_now

router = APIRouter(prefix="/api")

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_MAX_PIXELS = 32_000_000


def _project(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root


def _portrait_paths(slug: str, character: str) -> tuple[Path, Path, str]:
    name = character.strip()
    if not name:
        raise ValueError("Character name is required")
    root = _project(slug)
    key = slugify(name)
    folder = root / "characters" / "assets"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}.png", folder / f"{key}.json", f"characters/assets/{key}.png"


def _load_image(raw: bytes) -> Image.Image:
    if not raw:
        raise ValueError("Image is empty")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise ValueError("Image exceeds the 20 MB project asset limit")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded data is not a supported image") from exc
    if image.width * image.height > _MAX_PIXELS:
        raise ValueError("Image dimensions are too large")
    return image.convert("RGB")


def _save_portrait(
    slug: str,
    character: str,
    image: Image.Image,
    *,
    source: str,
    prompt: str = "",
) -> dict:
    image_path, metadata_path, relative_path = _portrait_paths(slug, character)
    image.save(image_path, format="PNG", optimize=True)
    metadata = {
        "character": character.strip(),
        "relative_path": relative_path,
        "source": source,
        "prompt": prompt,
        "width": image.width,
        "height": image.height,
        "generated_at": utc_now(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


@router.get(
    "/projects/{slug}/character-portraits/{character}/metadata",
    response_model=CharacterPortraitResponse,
)
def portrait_metadata(slug: str, character: str) -> dict:
    try:
        image_path, metadata_path, _ = _portrait_paths(slug, character)
        if not image_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(character)
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character portrait not found") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/character-portraits/{character}")
def portrait_image(slug: str, character: str) -> FileResponse:
    try:
        image_path, _, _ = _portrait_paths(slug, character)
        if not image_path.exists():
            raise FileNotFoundError(character)
        return FileResponse(
            image_path,
            media_type="image/png",
            filename=image_path.name,
            headers={"Cache-Control": "no-store"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character portrait not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/character-portraits/{character}/upload",
    response_model=CharacterPortraitResponse,
)
async def upload_portrait(
    slug: str,
    character: str,
    image: Annotated[UploadFile, File()],
) -> dict:
    try:
        raw = await image.read(_MAX_UPLOAD_BYTES + 1)
        portrait = _load_image(raw)
        return _save_portrait(slug, character, portrait, source="upload")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/character-portraits/generate",
    response_model=CharacterPortraitResponse,
)
async def generate_portrait(slug: str, payload: CharacterPortraitGenerateRequest) -> dict:
    try:
        _project(slug)
        base_url = payload.base_url.rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Stable Diffusion server must be an http(s) URL")
        body: dict[str, object] = {
            "prompt": payload.prompt,
            "negative_prompt": payload.negative_prompt,
            "width": payload.width,
            "height": payload.height,
            "steps": payload.steps,
            "cfg_scale": payload.cfg_scale,
            "seed": payload.seed,
            "batch_size": 1,
            "n_iter": 1,
        }
        if payload.sampler_name:
            body["sampler_name"] = payload.sampler_name
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            response = await client.post(f"{base_url}/sdapi/v1/txt2img", json=body)
            response.raise_for_status()
        data = response.json()
        encoded = (data.get("images") or [None])[0]
        if not isinstance(encoded, str) or not encoded:
            raise RuntimeError("Stable Diffusion returned no image")
        if "," in encoded and encoded.lstrip().startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Stable Diffusion returned invalid image data") from exc
        portrait = _load_image(raw)
        return _save_portrait(
            slug,
            payload.character,
            portrait,
            source="stable_diffusion_webui",
            prompt=payload.prompt,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Stable Diffusion server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/projects/{slug}/character-portraits/{character}", status_code=204)
def delete_portrait(slug: str, character: str) -> None:
    try:
        image_path, metadata_path, _ = _portrait_paths(slug, character)
        if not image_path.exists() and not metadata_path.exists():
            raise FileNotFoundError(character)
        image_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character portrait not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
