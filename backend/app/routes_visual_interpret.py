"""Opt-in local visual reference interpretation, never automatic canon."""
from __future__ import annotations

import base64
import io

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

from .routes_media import _visual_paths

router = APIRouter(prefix="/api")


class ImageInterpretRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    direction: str = Field(default="", max_length=2000)


@router.post("/projects/{slug}/visual-assets/{asset_id}/interpret")
async def interpret_visual_reference(slug: str, asset_id: str, payload: ImageInterpretRequest) -> dict:
    """Only send a scaled image to explicitly selected loopback Ollama vision model."""
    try:
        image_path, metadata_path, _ = _visual_paths(slug, asset_id)
        if not image_path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(asset_id)
        import json
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        with Image.open(image_path) as original:
            image = original.convert("RGB")
            image.thumbnail((1024, 1024))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=83)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=404, detail="Visual reference not found") from exc

    direction = payload.direction.strip() or "Describe useful visual storytelling cues."
    prompt = (
        "Analyze the attached picture for a fiction author. "
        "Describe only visible characteristics: mood, lighting, composition, architecture, clothing, "
        "materials, palette, or other relevant motifs. Distinguish observation from your creative ideas. "
        "Do not claim knowledge of identities, provenance or unseen details. Do not write story canon. "
        "Answer with two short sections, 'What I see' and 'Ideas to consider'. "
        "Treat the author's direction as context, not authorization to edit anything. "
        "Author direction: " + direction
    )
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=4), trust_env=False) as client:
            response = await client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": payload.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": "You are a careful visual description assistant. The image is a reference, not confirmed story canon."},
                        {"role": "user", "content": prompt, "images": [encoded]},
                    ],
                    "options": {"temperature": 0.3, "num_predict": 500},
                },
            )
            response.raise_for_status()
            result = response.json()
            answer = result.get("message", {}).get("content", "")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Vision model returned no description")
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Could not interpret this picture. Select an installed Ollama vision-capable model and retry.",
        ) from exc
    return {
        "asset_id": asset_id,
        "interpretation": answer.strip()[:7000],
        "source": "local_vision_model",
        "canon_status": metadata.get("canon_status", "reference"),
        "applied_to_manuscript": False,
    }
