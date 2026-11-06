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

class KokoroVoice(BaseModel):
    character: str = Field(min_length=1, max_length=100)
    voice_id: str = Field(min_length=1, max_length=80)
    speed: float = Field(default=1.0, ge=0.7, le=1.4)


class KokoroScene(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


@router.get("/kokoro/expression-capabilities")
def kokoro_expression_capabilities() -> dict:
    from .expressive_prosody import capabilities
    return capabilities()


class KittenVoice(BaseModel):
    character: str = Field(min_length=1, max_length=100)
    voice_id: str = Field(min_length=1, max_length=80)


class KittenProof(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)


@router.get("/kitten/status")
def kitten_status() -> dict:
    from .kitten_local import status
    return status()


@router.get("/kitten/voices")
def kitten_voices() -> dict:
    from .kitten_local import voice_ids
    try:
        return {"voices": voice_ids()}
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.get("/kitten/profiles")
def kitten_profiles(slug: str) -> dict:
    from .kitten_local import library
    try:
        return library(slug)
    except (OSError, ValueError) as exc:
        fail(exc)


@router.put("/kitten/profiles")
def kitten_save_profile(slug: str, payload: KittenVoice) -> dict:
    from .kitten_local import save_profile
    try:
        return save_profile(slug, payload.character, payload.voice_id)
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.post("/kitten/rehearsals")
async def kitten_rehearse(slug: str, payload: KittenProof) -> dict:
    import asyncio
    from .kitten_local import render_line
    from .local_resources import reservation
    try:
        async with reservation():
            return await asyncio.to_thread(render_line, slug, payload.path, payload.start)
    except ImportError as exc:
        raise HTTPException(503, "Optional KittenTTS 2 and audio dependencies are not installed") from exc
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.get("/kitten/rehearsals/{filename}")
def kitten_rehearsal_audio(slug: str, filename: str) -> FileResponse:
    from .kitten_local import take_file
    try:
        return FileResponse(take_file(slug, filename), media_type="audio/wav")
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/kokoro/status")
def kokoro_status() -> dict:
    from .kokoro_local import status
    return status()


@router.get("/kokoro/voices")
def kokoro_profiles(slug: str) -> dict:
    from .kokoro_local import library
    try:
        return library(slug)
    except (OSError, ValueError) as exc:
        fail(exc)


@router.put("/kokoro/voices")
def kokoro_save_profile(slug: str, payload: KokoroVoice) -> dict:
    from .kokoro_local import save_profile
    try:
        return save_profile(slug, payload.character, payload.voice_id, payload.speed)
    except (OSError, ValueError) as exc:
        fail(exc)


@router.post("/kokoro/scene-plan")
def kokoro_scene_plan(slug: str, payload: KokoroScene) -> dict:
    from .kokoro_local import scene_plan
    try:
        return scene_plan(slug, payload.path, payload.start, payload.end)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.post("/kokoro/rehearsals")
def kokoro_scene_rehearsal(slug: str, payload: KokoroScene) -> dict:
    from .kokoro_local import render_scene
    try:
        return render_scene(slug, payload.path, payload.start, payload.end)
    except ImportError as exc:
        raise HTTPException(503, "Optional Kokoro ONNX dependencies are not installed") from exc
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/kokoro/rehearsals/{filename}")
def kokoro_scene_audio(slug: str, filename: str) -> FileResponse:
    from .kokoro_local import rehearsal_file
    try:
        return FileResponse(rehearsal_file(slug, filename), media_type="audio/wav")
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.get("/kokoro/book")
def neural_book_status(slug: str) -> dict:
    from .kokoro_book import status
    try:
        return status(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


class NeuralBatchStart(BaseModel):
    engine: str = Field(default="kokoro-onnx", pattern=r"^(kokoro-onnx|kitten-tts-2)$")


@router.post("/kokoro/book")
def neural_book_start(slug: str, payload: NeuralBatchStart | None = None) -> dict:
    from .kokoro_book import start
    try:
        return start(slug, engine=payload.engine if payload is not None else "kokoro-onnx")
    except ImportError as exc:
        raise HTTPException(503, "Selected optional local speech engine is not installed") from exc
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.post("/kokoro/book/next")
async def neural_book_next(slug: str) -> dict:
    from .kokoro_book import advance
    try:
        return await advance(slug)
    except ImportError as exc:
        raise HTTPException(503, "Optional local neural speech engine dependencies are not installed") from exc
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.get("/kokoro/book/audio/{filename}")
def neural_book_audio(slug: str, filename: str) -> FileResponse:
    from .kokoro_book import chapter_audio
    try:
        return FileResponse(chapter_audio(slug, filename), media_type="audio/wav")
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

class NeuralProofDecision(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    listened_seconds: float = Field(ge=0)
    full_listen: bool
    source_aligned: bool


class NeuralChapterAction(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class NeuralRetakeAction(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    segment: int = Field(ge=0)


@router.get("/kokoro/book/proof")
def neural_proof_status(slug: str) -> dict:
    from .kokoro_finishing import proof_status
    try:
        return proof_status(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/kokoro/book/proof")
def neural_proof_approve(slug: str, payload: NeuralProofDecision) -> dict:
    from .kokoro_finishing import approve
    try:
        return approve(slug, payload.path, payload.listened_seconds,
                       payload.full_listen, payload.source_aligned)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.delete("/kokoro/book/proof")
def neural_proof_revoke(slug: str, payload: NeuralChapterAction) -> dict:
    from .kokoro_finishing import revoke
    try:
        return revoke(slug, payload.path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/kokoro/book/segments")
def neural_book_segments(slug: str, path: str) -> dict:
    from .kokoro_finishing import segment_list
    try:
        return segment_list(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.post("/kokoro/book/retake")
async def neural_book_retake(slug: str, payload: NeuralRetakeAction) -> dict:
    from .kokoro_finishing import retake
    try:
        return await retake(slug, payload.path, payload.segment)
    except ImportError as exc:
        raise HTTPException(503, "Install optional Kokoro ONNX engine to retake audio") from exc
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        fail(exc)


@router.post("/kokoro/book/export")
def neural_book_export(slug: str) -> dict:
    from .kokoro_finishing import export
    try:
        return export(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/kokoro/book/export/{filename}")
def neural_book_archive(slug: str, filename: str) -> FileResponse:
    from .kokoro_finishing import export_file
    try:
        return FileResponse(export_file(slug, filename),
                            media_type="application/zip", filename=filename)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)

@router.post("/kokoro/book/export-m4b")
async def neural_book_export_m4b(slug: str) -> dict:
    import asyncio

    from .kokoro_finishing import export_m4b
    try:
        return await asyncio.to_thread(export_m4b, slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/kokoro/book/export-m4b/{filename}")
def neural_book_m4b_download(slug: str, filename: str) -> FileResponse:
    from .kokoro_finishing import m4b_file
    try:
        return FileResponse(m4b_file(slug, filename), media_type="audio/mp4", filename=filename)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


class IpaRule(BaseModel):
    written: str = Field(min_length=1, max_length=80)
    ipa: str = Field(min_length=1, max_length=100)


@router.get("/pronunciation-reference")
def pronunciation_reference() -> dict:
    from .pronunciation_lexicon import reference_examples

    return reference_examples()


@router.put("/ipa-pronunciations")
def save_ipa_term(slug: str, payload: IpaRule) -> dict:
    try:
        return audio_production.save_ipa_pronunciation(slug, payload.written, payload.ipa)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.delete("/ipa-pronunciations/{written}")
def delete_ipa_term(slug: str, written: str) -> dict:
    try:
        return audio_production.delete_ipa_pronunciation(slug, written)
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.get("/pronunciation-dictionary")
def pronunciation_dictionary(word: str) -> dict:
    from .pronunciation_lexicon import dictionary_lookup

    try:
        return dictionary_lookup(word)
    except ValueError as exc:
        fail(exc)

class PerformanceVoiceEdit(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    speaker: str = Field(min_length=1, max_length=100)


class PerformanceDirectionEdit(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    emotion: str = Field(min_length=1, max_length=40)
    delivery: str = Field(min_length=1, max_length=140)
    energy: int = Field(default=3, ge=1, le=5)


def _performance_source(slug: str, path: str):
    from pathlib import Path
    from . import audio_director
    from .audiobook_local import _spoken_text, available_chapters
    from .storage import project_root, read_text
    if path not in {row["path"] for row in available_chapters(slug)}:
        raise FileNotFoundError("Select an existing manuscript chapter")
    source = _spoken_text(read_text(slug, path))
    data = audio_production.load(slug)
    names = sorted(set(["Narrator"])
                   | set(data.get("kokoro_voices", {}))
                   | set(data.get("neural_voices", {}))
                   | set(data.get("character_voices", {}))
                   | {row["character"] for row in data.get("chapter_casts", {}).get(path, [])
                      if row.get("character")})
    dest = project_root(slug) / ".ember" / "audio-director" / (Path(path).stem + ".performance.json")
    performance = audio_director.load_or_compile(
        dest, source, names, data.get("chapter_casts", {}).get(path, []))
    return performance, dest, names


@router.get("/performance")
def get_performance_script(slug: str, path: str) -> dict:
    """Read the lossless audiobook-only cue sheet and unresolved speaker list."""
    try:
        performance, _, names = _performance_source(slug, path)
        return performance
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/performance/speaker")
def save_performance_speaker(slug: str, payload: PerformanceVoiceEdit) -> dict:
    from .audio_director import revise_speaker, save_performance
    try:
        performance, dest, names = _performance_source(slug, payload.path)
        performance = revise_speaker(
            performance, payload.start, payload.end, payload.speaker, names)
        save_performance(dest, performance)
        return performance
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)


@router.put("/performance/direction")
def save_performance_direction(slug: str, payload: PerformanceDirectionEdit) -> dict:
    from .audio_director import revise_direction, save_performance
    try:
        performance, dest, _ = _performance_source(slug, payload.path)
        performance = revise_direction(
            performance, payload.start, payload.end, payload.emotion, payload.delivery,
            payload.energy)
        save_performance(dest, performance)
        return performance
    except (FileNotFoundError, OSError, ValueError) as exc:
        fail(exc)
