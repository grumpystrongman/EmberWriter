"""Author-owned offline narration planning and proof-listening API."""
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import audio_production

router = APIRouter(prefix="/api/projects/{slug}/audiobook-production", tags=["Audiobook Production"])

class Rule(BaseModel):
    written: str = Field(min_length=2, max_length=90)
    spoken: str = Field(min_length=1, max_length=140)

class Profile(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    voice: str = Field(default="", max_length=110)
    rate: int = Field(default=-1, ge=-5, le=5)

class CharacterVoice(BaseModel):
    character: str = Field(min_length=1, max_length=100)
    voice: str = Field(min_length=1, max_length=110)
    rate: int = Field(default=-1, ge=-5, le=5)

class Cast(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=20000)
    voice: str = Field(default="", max_length=110)
    character: str = Field(default="", max_length=100)

class Note(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    seconds: float = Field(ge=0, le=200000)
    note: str = Field(min_length=4, max_length=1000)

class Decision(BaseModel):
    resolved: bool

class Approval(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    listened_seconds: float = Field(gt=0, le=200000)
    source_aligned: bool
    full_listen: bool

def fail(exc):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    raise HTTPException(409, str(exc)) from exc

@router.get("")
def get(slug: str) -> dict:
    try:
        return audio_production.load(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.put("/pronunciations")
def save_term(slug: str, payload: Rule) -> dict:
    try:
        return audio_production.save_pronunciation(slug, payload.written, payload.spoken)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.delete("/pronunciations/{written}")
def delete_term(slug: str, written: str) -> dict:
    try:
        return audio_production.delete_pronunciation(slug, written)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.put("/profiles")
def save_profile(slug: str, payload: Profile) -> dict:
    try:
        return audio_production.save_profile(slug, payload.path, payload.voice, payload.rate)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.delete("/profiles")
def delete_profile(slug: str, path: str) -> dict:
    try:
        return audio_production.delete_profile(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.post("/notes")
def add_note(slug: str, payload: Note) -> dict:
    try:
        return audio_production.add_note(slug, payload.path, payload.seconds, payload.note)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.post("/notes/{note_id}")
def resolve_note(slug: str, note_id: str, payload: Decision) -> dict:
    try:
        return audio_production.resolve_note(slug, note_id, payload.resolved)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.post("/proof-approvals")
def approve_proof(slug: str, payload: Approval) -> dict:
    from .proof_approval import approve
    try:
        return approve(slug, payload.path, payload.listened_seconds,
                       payload.source_aligned, payload.full_listen)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.delete("/proof-approvals")
def revoke_proof(slug: str, path: str) -> dict:
    from .proof_approval import revoke
    try:
        return revoke(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/characters")
def upsert_character_voice(slug: str, payload: CharacterVoice) -> dict:
    try:
        return audio_production.save_character_voice(slug, payload.character, payload.voice, payload.rate)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.delete("/characters")
def remove_character_voice(slug: str, character: str) -> dict:
    try:
        return audio_production.delete_character_voice(slug, character)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/casting-suggestions")
def casting_suggestions(slug: str, path: str) -> dict:
    try:
        return audio_production.suggest_casts(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/casting")
def add_character_cast(slug: str, payload: Cast) -> dict:
    try:
        return audio_production.save_cast(slug, payload.path, payload.start,
                                          payload.end, payload.text, payload.voice, payload.character)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.delete("/casting")
def clear_character_casts(slug: str, path: str) -> dict:
    try:
        return audio_production.clear_casts(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


class NeuralVoice(BaseModel):
    character: str = Field(min_length=1, max_length=100)
    reference_id: str = Field(min_length=1, max_length=80)
    direction: str = Field(default="", max_length=500)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)


class NeuralTake(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    port: int = Field(default=8080, ge=1024, le=65535)


@router.get("/neural-voices")
def neural_voices(slug: str) -> dict:
    from .audio_drama import voice_library
    try:
        return voice_library(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/neural-voices")
def neural_voice(slug: str, payload: NeuralVoice) -> dict:
    from .audio_drama import save_voice
    try:
        return save_voice(slug, payload.character, payload.reference_id,
                          payload.direction, payload.seed)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/production-readiness")
def get_production_readiness(slug: str) -> dict:
    from .audio_drama import production_readiness
    try:
        return production_readiness(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/neural-production-plan")
def neural_production_plan(slug: str) -> dict:
    from .audio_drama import production_plan
    try:
        return production_plan(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/neural-health")
def neural_health(port: int = 8080) -> dict:
    from .audio_drama import local_health
    try:
        return local_health(port)
    except ValueError as exc:
        fail(exc)


@router.post("/neural-takes")
def neural_take(slug: str, payload: NeuralTake) -> dict:
    from .audio_drama import render_take
    try:
        return render_take(slug, payload.path, payload.start, payload.port)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Local Fish Speech server is unavailable or rejected the proof take") from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/neural-takes/{filename}")
def neural_take_audio(slug: str, filename: str) -> FileResponse:
    from .audio_drama import take_file
    try:
        return FileResponse(take_file(slug, filename), media_type="audio/wav")
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)
