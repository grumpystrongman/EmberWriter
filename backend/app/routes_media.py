from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from .atlas import load_atlas
from .generation import build_messages, generate
from .media_models import (
    CharacterPortraitGenerateRequest,
    CharacterPortraitResponse,
    VisualAssetGenerateRequest,
    VisualAssetResponse,
    VisualAssetUpdate,
    VisualPromptRequest,
    VisualPromptResponse,
)
from .memory import list_memory
from .storage import _touch_project, project_root, slugify, utc_now

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


def _visual_paths(slug: str, asset_id: str) -> tuple[Path, Path, str]:
    key = asset_id.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
        raise ValueError(
            "Visual asset id must contain only lowercase letters, numbers, and hyphens"
        )
    root = _project(slug)
    folder = root / "assets" / "visuals"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}.png", folder / f"{key}.json", f"assets/visuals/{key}.png"


def _ensure_visual_id_available(slug: str, asset_id: str) -> None:
    image_path, metadata_path, _ = _visual_paths(slug, asset_id)
    if image_path.exists() or metadata_path.exists():
        raise ValueError(
            f"Visual asset already exists: {asset_id}. Choose a new asset id to preserve the existing reference."
        )


def _validate_reference_asset(slug: str, asset_id: str, reference_asset_id: str) -> Path:
    normalized_asset = asset_id.strip().lower()
    normalized_reference = reference_asset_id.strip().lower()
    if normalized_asset == normalized_reference:
        raise ValueError("A visual asset cannot reference itself")
    reference_path, reference_metadata, _ = _visual_paths(slug, normalized_reference)
    if not reference_path.exists() or not reference_metadata.exists():
        raise ValueError(f"Reference visual asset not found: {reference_asset_id}")
    return reference_path


def _visual_asset_dependencies(slug: str, asset_id: str) -> list[str]:
    root = _project(slug)
    normalized = asset_id.strip().lower()
    dependencies: list[str] = []
    visuals_dir = root / "assets" / "visuals"
    if visuals_dir.exists():
        for metadata_path in sorted(visuals_dir.glob("*.json")):
            if metadata_path.stem == normalized:
                continue
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if str(payload.get("reference_asset_id") or "").strip().lower() == normalized:
                dependencies.append(f"visual:{metadata_path.stem}")
    try:
        atlas = load_atlas(slug)
    except FileNotFoundError:
        atlas = None
    if atlas is not None:
        if str(atlas.map.background_asset_id or "").strip().lower() == normalized:
            dependencies.append("atlas:map-background")
        for location in atlas.locations:
            if str(location.image_asset_id or "").strip().lower() == normalized:
                dependencies.append(f"atlas:location:{location.id}")
    return list(dict.fromkeys(dependencies))


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
    _touch_project(slug)
    return metadata


def _save_visual_asset(
    slug: str,
    asset_id: str,
    image: Image.Image,
    *,
    title: str,
    kind: str,
    source: str,
    prompt: str = "",
    negative_prompt: str = "",
    canon_status: str = "concept",
    linked_entities: list[str] | None = None,
    notes: str = "",
    reference_asset_id: str | None = None,
) -> dict:
    _ensure_visual_id_available(slug, asset_id)
    image_path, metadata_path, relative_path = _visual_paths(slug, asset_id)
    image.save(image_path, format="PNG", optimize=True)
    metadata = {
        "asset_id": asset_id.strip().lower(),
        "title": title.strip() or asset_id,
        "kind": kind.strip() or "reference",
        "relative_path": relative_path,
        "source": source,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": image.width,
        "height": image.height,
        "generated_at": utc_now(),
        "canon_status": canon_status,
        "linked_entities": list(
            dict.fromkeys(
                item.strip() for item in (linked_entities or []) if item.strip()
            )
        ),
        "notes": notes,
        "reference_asset_id": reference_asset_id,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _touch_project(slug)
    return metadata


def _image_as_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def _stable_diffusion_image(
    *,
    base_url: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    seed: int,
    sampler_name: str | None,
    init_image: Image.Image | None = None,
    denoising_strength: float = 0.45,
) -> Image.Image:
    normalized_url = base_url.rstrip("/")
    if not normalized_url.startswith(("http://", "https://")):
        raise ValueError("Stable Diffusion server must be an http(s) URL")
    body: dict[str, object] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
        "batch_size": 1,
        "n_iter": 1,
    }
    if sampler_name:
        body["sampler_name"] = sampler_name
    endpoint = "txt2img"
    if init_image is not None:
        endpoint = "img2img"
        body["init_images"] = [_image_as_base64(init_image)]
        body["denoising_strength"] = denoising_strength
        body["resize_mode"] = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        response = await client.post(
            f"{normalized_url}/sdapi/v1/{endpoint}", json=body
        )
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
    return _load_image(raw)


def _json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _visual_context(slug: str, subject: str) -> tuple[str, list[str]]:
    facts = list_memory(
        slug,
        query=subject,
        kinds=[
            "canon",
            "location",
            "character_state",
            "character_knowledge",
            "timeline",
            "object",
            "ability",
            "relationship",
        ],
        limit=80,
    )
    sources = list(
        dict.fromkeys(item["source_path"] for item in facts if item.get("source_path"))
    )
    payload = [
        {
            "kind": item["kind"],
            "subject": item["subject"],
            "predicate": item["predicate"],
            "object": item["object"],
            "chapter": item["chapter_order"],
            "source": item["source_path"],
        }
        for item in facts
    ]
    root = _project(slug)
    world_notes: list[dict[str, str]] = []
    remaining = 12000
    world_root = root / "world"
    for path in sorted(world_root.glob("*.md")) if world_root.exists() else []:
        if remaining <= 0:
            break
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        if (
            subject.casefold() not in text.casefold()
            and subject.casefold() not in path.stem.casefold()
        ):
            continue
        excerpt = text[: min(4000, remaining)]
        remaining -= len(excerpt)
        relative = str(path.relative_to(root)).replace("\\", "/")
        sources.append(relative)
        world_notes.append({"path": relative, "content": excerpt})

    atlas_payload: dict[str, Any] = {}
    try:
        atlas = load_atlas(slug)
        subject_folded = subject.casefold()
        matched_locations = [
            item.model_dump(mode="json")
            for item in atlas.locations
            if subject_folded in item.name.casefold()
            or item.name.casefold() in subject_folded
        ]
        matched_ids = {item["id"] for item in matched_locations}
        matched_connections = [
            item.model_dump(mode="json")
            for item in atlas.connections
            if item.from_id in matched_ids or item.to_id in matched_ids
        ]
        atlas_payload = {
            "locations": matched_locations,
            "connections": matched_connections,
        }
    except (FileNotFoundError, ValueError):
        atlas_payload = {}

    canonical_visuals: list[dict[str, Any]] = []
    visuals_dir = root / "assets" / "visuals"
    if visuals_dir.exists():
        for metadata_path in sorted(visuals_dir.glob("*.json")):
            try:
                visual = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            linked = [
                str(item).casefold() for item in visual.get("linked_entities", [])
            ]
            if visual.get("canon_status") != "canonical":
                continue
            if (
                subject.casefold() not in linked
                and subject.casefold()
                not in str(visual.get("title", "")).casefold()
            ):
                continue
            canonical_visuals.append(
                {
                    "asset_id": visual.get("asset_id", metadata_path.stem),
                    "title": visual.get("title", ""),
                    "kind": visual.get("kind", ""),
                    "prompt": visual.get("prompt", ""),
                    "notes": visual.get("notes", ""),
                }
            )

    return json.dumps(
        {
            "memory": payload,
            "world_notes": world_notes,
            "atlas": atlas_payload,
            "canonical_visuals": canonical_visuals,
        },
        ensure_ascii=False,
    ), list(dict.fromkeys(sources))


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
        portrait = await _stable_diffusion_image(
            base_url=payload.base_url,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            cfg_scale=payload.cfg_scale,
            seed=payload.seed,
            sampler_name=payload.sampler_name,
        )
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
        raise HTTPException(
            status_code=502, detail=f"Stable Diffusion server error: {exc}"
        ) from exc
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
        _touch_project(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Character portrait not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/visual-assets", response_model=list[VisualAssetResponse])
def list_visual_assets(slug: str) -> list[dict]:
    try:
        folder = _project(slug) / "assets" / "visuals"
        if not folder.exists():
            return []
        assets: list[dict] = []
        for metadata_path in sorted(folder.glob("*.json")):
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                image_path = folder / f"{metadata_path.stem}.png"
                if image_path.exists():
                    assets.append(
                        VisualAssetResponse.model_validate(payload).model_dump(mode="json")
                    )
            except (json.JSONDecodeError, ValueError):
                continue
        assets.sort(key=lambda item: item.get("generated_at", ""), reverse=True)
        return assets
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get(
    "/projects/{slug}/visual-assets/{asset_id}/metadata",
    response_model=VisualAssetResponse,
)
def visual_asset_metadata(slug: str, asset_id: str) -> dict:
    try:
        image_path, metadata_path, _ = _visual_paths(slug, asset_id)
        if not image_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(asset_id)
        return VisualAssetResponse.model_validate_json(
            metadata_path.read_text(encoding="utf-8")
        ).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/visual-assets/{asset_id}")
def visual_asset_image(slug: str, asset_id: str) -> FileResponse:
    try:
        image_path, _, _ = _visual_paths(slug, asset_id)
        if not image_path.exists():
            raise FileNotFoundError(asset_id)
        return FileResponse(
            image_path,
            media_type="image/png",
            filename=image_path.name,
            headers={"Cache-Control": "no-store"},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/visual-assets/{asset_id}/upload",
    response_model=VisualAssetResponse,
)
async def upload_visual_asset(
    slug: str,
    asset_id: str,
    image: Annotated[UploadFile, File()],
    title: str = Query(default="", max_length=240),
    kind: str = Query(default="reference", max_length=80),
) -> dict:
    try:
        _ensure_visual_id_available(slug, asset_id)
        raw = await image.read(_MAX_UPLOAD_BYTES + 1)
        visual = _load_image(raw)
        return _save_visual_asset(
            slug,
            asset_id,
            visual,
            title=title or asset_id,
            kind=kind,
            source="upload",
            canon_status="reference",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/visual-assets/generate", response_model=VisualAssetResponse
)
async def generate_visual_asset(
    slug: str, payload: VisualAssetGenerateRequest
) -> dict:
    try:
        _project(slug)
        _ensure_visual_id_available(slug, payload.asset_id)
        init_image = None
        if payload.reference_asset_id:
            reference_path = _validate_reference_asset(
                slug, payload.asset_id, payload.reference_asset_id
            )
            init_image = _load_image(reference_path.read_bytes())
        visual = await _stable_diffusion_image(
            base_url=payload.base_url,
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            width=payload.width,
            height=payload.height,
            steps=payload.steps,
            cfg_scale=payload.cfg_scale,
            seed=payload.seed,
            sampler_name=payload.sampler_name,
            init_image=init_image,
            denoising_strength=payload.denoising_strength,
        )
        return _save_visual_asset(
            slug,
            payload.asset_id,
            visual,
            title=payload.title,
            kind=payload.kind,
            source="stable_diffusion_webui",
            prompt=payload.prompt,
            negative_prompt=payload.negative_prompt,
            canon_status=payload.canon_status,
            linked_entities=payload.linked_entities,
            reference_asset_id=payload.reference_asset_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Stable Diffusion server error: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put(
    "/projects/{slug}/visual-assets/{asset_id}/metadata",
    response_model=VisualAssetResponse,
)
def update_visual_asset_metadata(
    slug: str, asset_id: str, payload: VisualAssetUpdate
) -> dict:
    try:
        image_path, metadata_path, _ = _visual_paths(slug, asset_id)
        if not image_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(asset_id)
        current = VisualAssetResponse.model_validate_json(
            metadata_path.read_text(encoding="utf-8")
        ).model_dump(mode="json")
        updates = payload.model_dump(exclude_unset=True, mode="json")
        if "reference_asset_id" in updates and updates["reference_asset_id"] is not None:
            _validate_reference_asset(slug, asset_id, str(updates["reference_asset_id"]))
        current.update(updates)
        normalized = VisualAssetResponse.model_validate(current)
        metadata_path.write_text(
            json.dumps(normalized.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _touch_project(slug)
        return normalized.model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{slug}/visual-assets/{asset_id}", status_code=204)
def delete_visual_asset(slug: str, asset_id: str) -> None:
    try:
        image_path, metadata_path, _ = _visual_paths(slug, asset_id)
        if not image_path.exists() and not metadata_path.exists():
            raise FileNotFoundError(asset_id)
        dependencies = _visual_asset_dependencies(slug, asset_id)
        if dependencies:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Visual asset is still referenced by: "
                    + ", ".join(dependencies[:20])
                    + ". Remove those references before deleting it."
                ),
            )
        image_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        _touch_project(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Visual asset not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/visual-assets/compose-prompt",
    response_model=VisualPromptResponse,
)
async def compose_visual_prompt(
    slug: str, payload: VisualPromptRequest
) -> VisualPromptResponse:
    try:
        _project(slug)
        context, sources = _visual_context(slug, payload.subject)
        instruction = f"""Create a production-ready image generation prompt for a fiction reference image.
Subject: {payload.subject}
Kind: {payload.kind}
Story chapter/time context: {payload.chapter}
Author direction: {payload.instruction or 'Create a faithful, useful visual reference.'}

Use only established visual facts as facts. Do not silently invent canon. You may add composition, lighting, camera, texture, and mood choices, but keep them stylistic rather than new story facts. If the canon is incomplete, make the visual choice neutral and mention the uncertainty in continuity_notes. Reuse relevant canonical visual prompt details when supplied so recurring people and places stay visually consistent.

Return ONLY JSON:
{{"prompt":"detailed positive prompt","negative_prompt":"things to avoid, including contradictions","continuity_notes":["canon or uncertainty note"]}}"""
        text = await generate(
            payload.provider,
            build_messages("brainstorm", instruction, context),
            temperature=0.55,
            top_p=0.9,
            json_mode=True,
        )
        parsed = _json_object(text)
        if parsed is None:
            return VisualPromptResponse(
                prompt=text.strip(),
                context_sources=sources,
                continuity_notes=[
                    "The model returned an unstructured prompt; verify canon before marking the image canonical."
                ],
            )
        return VisualPromptResponse(
            prompt=str(parsed.get("prompt", "")).strip() or text.strip(),
            negative_prompt=str(parsed.get("negative_prompt", "")).strip(),
            continuity_notes=[
                str(item)
                for item in parsed.get("continuity_notes", [])
                if str(item).strip()
            ],
            context_sources=sources,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
