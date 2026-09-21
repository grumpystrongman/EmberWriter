from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Expected patch anchor not found in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# 1) Studio context: fresh and continuation are different contracts, and hard canon/craft stay early.
path = "backend/app/studio_context.py"
replace_once(
    path,
    """def build_studio_context(\n    slug: str,\n    prompt: str,\n    controls: CraftControls,\n    *,\n    max_chars: int = 42000,\n) -> tuple[str, list[str], str, list[str]]:\n""",
    """def build_studio_context(\n    slug: str,\n    prompt: str,\n    controls: CraftControls,\n    *,\n    max_chars: int = 42000,\n    continuation: bool = False,\n) -> tuple[str, list[str], str, list[str]]:\n""",
)
replace_once(
    path,
    '''    """Build Binder-aware context for a fresh generation.\n\n    Fresh Write/Studio generation starts from a blank prose boundary. Binder material is reference\n    knowledge only: world, environment, characters, behavior, relationships, timeline, research,\n    notes, style, summaries, and other author-provided reference material can inform the new scene,\n    but Draft/manuscript prose is never supplied as something to continue. Explicit Continue mode is\n    handled elsewhere and is the only mode that receives the current manuscript ending.\n    """\n    sections: list[str] = [\n        (\n            "## Fresh generation boundary\\n"\n            "Start the requested prose from a NEW first line. Do not continue, complete, quote, or imitate the ending of a prior scene. "\n            "Everything below is reference knowledge only. Use it to preserve canon, environment, character behavior, voice, relationships, "\n            "world rules, and continuity while beginning the exact new scene requested by the author."\n        )\n    ]\n''',
    '''    """Build Binder-aware context for a fresh Studio scene or an explicit Studio continuation.\n\n    Binder material is reference knowledge only. Fresh Write starts from a blank prose boundary.\n    Continue receives its exact Studio draft handoff in the author instruction and must resume that\n    handoff rather than treating Binder material as prose to continue.\n    """\n    heat = controls.heat_level or "project default"\n    if continuation:\n        boundary = (\n            "## Studio continuation boundary\\n"\n            "STUDIO SCENE DELIVERY CONTRACT:\\n"\n            f"Requested Studio heat: {heat}.\\n"\n            "Continue from the existing Studio draft supplied in AUTHOR INSTRUCTION. Do not start a new scene, "\n            "restart the setup, recap, paraphrase, or treat any Binder reference as the continuation target. "\n            "Everything below is reference knowledge only and exists to preserve canon, character behavior, voice, "\n            "relationships, world rules, and embodiment while the prose advances from the exact handoff."\n        )\n    else:\n        boundary = (\n            "## Fresh generation boundary\\n"\n            "STUDIO SCENE DELIVERY CONTRACT:\\n"\n            f"Requested Studio heat: {heat}.\\n"\n            "Start the requested prose from a NEW first line. Do not continue, complete, quote, or imitate the ending "\n            "of a prior scene. Everything below is reference knowledge only. Use it to preserve canon, environment, "\n            "character behavior, voice, relationships, world rules, and continuity while beginning the exact new scene "\n            "requested by the author."\n        )\n    sections: list[str] = [boundary]\n''',
)
replace_once(
    path,
    '''    context = _CONTEXT_SEPARATOR.join(section for section in sections if section).strip()\n''',
    '''    # Keep participant hard canon and the active craft/heat contract ahead of lower-priority catalog\n    # material so local-model context trimming cannot silently drop embodiment or delivery constraints.\n    priority_prefixes = ("## Character intelligence", "## Prose craft direction")\n    priority = [section for section in sections[1:] if section.startswith(priority_prefixes)]\n    remainder = [section for section in sections[1:] if section not in priority]\n    sections = [sections[0], *priority, *remainder]\n\n    context = _CONTEXT_SEPARATOR.join(section for section in sections if section).strip()\n''',
)

# 2) Streaming engine: verifier is explicit Studio state, sees heat/canon, and fails closed.
path = "backend/app/streaming_generation.py"
replace_once(path, '_VERIFIER_CONTEXT_CHARS = 16000\n', '_VERIFIER_CONTEXT_CHARS = 36000\n')
replace_once(
    path,
    '_STUDIO_CONTRACT_MARKER = "STUDIO SCENE DELIVERY CONTRACT:"\n',
    '_STUDIO_CONTRACT_MARKERS = ("STUDIO SCENE DELIVERY CONTRACT:", "STUDIO CONTINUATION CONTRACT:")\n',
)
replace_once(
    path,
    '''class RepetitionLoopDetected(RuntimeError):\n    """Raised when a live model stream starts recycling the same paragraph-level beat."""\n\n\n''',
    '''class RepetitionLoopDetected(RuntimeError):\n    """Raised when a live model stream starts recycling the same paragraph-level beat."""\n\n\nclass StudioDeliveryIncomplete(RuntimeError):\n    """Raised when Studio exhausts its bounded passes without verified scene delivery."""\n\n    def __init__(self, partial_text: str, reason: str) -> None:\n        self.partial_text = partial_text.strip()\n        self.reason = reason.strip() or "Studio scene delivery was not independently verified."\n        super().__init__(self.reason)\n\n\n''',
)
replace_once(
    path,
    '''def _is_studio_scene(messages: list[dict[str, str]]) -> bool:\n    return any(_STUDIO_CONTRACT_MARKER in message.get("content", "") for message in messages)\n\n\ndef _verifier_source_context(messages: list[dict[str, str]]) -> str:\n    user_messages = [message.get("content", "") for message in messages if message.get("role") == "user"]\n    if not user_messages:\n        return ""\n    return user_messages[0][:_VERIFIER_CONTEXT_CHARS]\n''',
    '''def _is_studio_scene(messages: list[dict[str, str]]) -> bool:\n    return any(\n        any(marker in message.get("content", "") for marker in _STUDIO_CONTRACT_MARKERS)\n        for message in messages\n    )\n\n\ndef _verifier_source_context(messages: list[dict[str, str]]) -> str:\n    system_messages = [message.get("content", "") for message in messages if message.get("role") == "system"]\n    user_messages = [message.get("content", "") for message in messages if message.get("role") == "user"]\n    pieces = [*system_messages[:1], *user_messages[:2]]\n    return "\\n\\n---\\n\\n".join(piece for piece in pieces if piece)[:_VERIFIER_CONTEXT_CHARS]\n''',
)
replace_once(
    path,
    '''async def verify_studio_scene_delivery(\n    config: ProviderConfig,\n    messages: list[dict[str, str]],\n    draft: str,\n) -> dict[str, object]:\n    """Use the configured local model as a strict independent delivery judge."""\n    request_context = _verifier_source_context(messages)\n''',
    '''async def verify_studio_scene_delivery(\n    config: ProviderConfig,\n    messages: list[dict[str, str]],\n    draft: str,\n    *,\n    heat_level: str | None = None,\n    verifier_context: str = "",\n) -> dict[str, object]:\n    """Use the configured local model as a strict independent delivery judge."""\n    request_context = verifier_context.strip() or _verifier_source_context(messages)\n    request_context = (\n        f"REQUESTED HEAT LEVEL: {heat_level or 'unspecified'}\\n"\n        f"{request_context}"\n    )[:_VERIFIER_CONTEXT_CHARS]\n''',
)
replace_once(
    path,
    '''async def generate_complete_prose_streamed(\n    config: ProviderConfig,\n    messages: list[dict[str, str]],\n    *,\n    min_words: int,\n    on_delta: DeltaCallback,\n    on_status: StatusCallback | None = None,\n    max_passes: int = 6,\n    max_output_tokens: int = 6144,\n) -> str:\n''',
    '''async def generate_complete_prose_streamed(\n    config: ProviderConfig,\n    messages: list[dict[str, str]],\n    *,\n    min_words: int,\n    on_delta: DeltaCallback,\n    on_status: StatusCallback | None = None,\n    max_passes: int = 6,\n    max_output_tokens: int = 6144,\n    studio_scene: bool | None = None,\n    heat_level: str | None = None,\n    verifier_context: str = "",\n) -> str:\n''',
)
replace_once(
    path,
    '    studio_delivery_verifier = marker_required and _is_studio_scene(messages)\n',
    '    studio_delivery_verifier = marker_required and (studio_scene if studio_scene is not None else _is_studio_scene(messages))\n',
)
replace_once(
    path,
    '                verdict = await verify_studio_scene_delivery(config, messages, accumulated)\n',
    '''                verdict = await verify_studio_scene_delivery(\n                    config,\n                    messages,\n                    accumulated,\n                    heat_level=heat_level,\n                    verifier_context=verifier_context,\n                )\n''',
)
replace_once(
    path,
    '''        if pass_index == max_passes - 1:\n            return accumulated\n''',
    '''        if pass_index == max_passes - 1:\n            if studio_delivery_verifier:\n                raise StudioDeliveryIncomplete(\n                    accumulated,\n                    verifier_reason or "Studio exhausted its completion passes without a verified ending.",\n                )\n            return accumulated\n''',
)

# 3) Generation route: continuation-aware Studio context, same verified engine for sync/stream, final Craft recheck.
path = "backend/app/routes_generation.py"
replace_once(
    path,
    'from .streaming_generation import generate_complete_prose_streamed, generate_streamed\n',
    '''from .streaming_generation import (\n    StudioDeliveryIncomplete,\n    generate_complete_prose_streamed,\n    generate_streamed,\n    verify_studio_scene_delivery,\n)\n''',
)
replace_once(
    path,
    '''        context_text, context_files, craft_text, _ = build_studio_context(\n            slug,\n            payload.prompt,\n            payload.craft,\n        )\n        return _cap_generation_context(context_text, max_chars=36000), context_files, craft_text\n''',
    '''        context_text, context_files, craft_text, _ = build_studio_context(\n            slug,\n            payload.prompt,\n            payload.craft,\n            continuation=payload.mode == "continue",\n        )\n        return _cap_generation_context(context_text, max_chars=52000), context_files, craft_text\n''',
)
# There are two streamed-generator call sites; patch both by replacing the common argument tail.
text = read(path)
old = '''                min_words=minimum_words,\n                on_delta=on_delta,\n                on_status=on_status,\n            )'''
new = '''                min_words=minimum_words,\n                on_delta=on_delta,\n                on_status=on_status,\n                studio_scene=_is_studio_request(payload),\n                heat_level=heat,\n                verifier_context=context_text if _is_studio_request(payload) else "",\n            )'''
if text.count(old) != 1:
    raise RuntimeError(f"Expected one _generate_payload streamed call anchor, found {text.count(old)}")
text = text.replace(old, new, 1)
old2 = '''                    min_words=minimum_words,\n                    on_delta=emit_delta,\n                    on_status=emit_status,\n                )'''
new2 = '''                    min_words=minimum_words,\n                    on_delta=emit_delta,\n                    on_status=emit_status,\n                    studio_scene=_is_studio_request(payload),\n                    heat_level=heat,\n                    verifier_context=context_text if _is_studio_request(payload) else "",\n                )'''
if text.count(old2) != 1:
    raise RuntimeError(f"Expected one stream producer call anchor, found {text.count(old2)}")
text = text.replace(old2, new2, 1)
write(path, text)
replace_once(
    path,
    '''    elif payload.mode in PROSE_MODES:\n        text = await generate_complete_prose(\n            payload.provider,\n            messages,\n            min_words=minimum_words,\n        )\n''',
    '''    elif payload.mode in PROSE_MODES:\n        if _is_studio_request(payload):\n            async def discard_delta(_text: str) -> None:\n                return None\n\n            text = await generate_complete_prose_streamed(\n                payload.provider,\n                messages,\n                min_words=minimum_words,\n                on_delta=discard_delta,\n                studio_scene=True,\n                heat_level=heat,\n                verifier_context=context_text,\n            )\n        else:\n            text = await generate_complete_prose(\n                payload.provider,\n                messages,\n                min_words=minimum_words,\n            )\n''',
)
# Patch both quality-pass blocks to preserve and re-verify the final author-facing Studio draft.
text = read(path)
needle = '''        targets = quality_guidance(text)\n        text = await quality_pass(\n'''
if text.count(needle) != 2:
    raise RuntimeError(f"Expected two quality pass blocks, found {text.count(needle)}")
text = text.replace(needle, '''        targets = quality_guidance(text)\n        pre_refine = text\n        text = await quality_pass(\n''')
quality_tail = '''        refined = True\n'''
replacement = '''        if _is_studio_request(payload):\n            verdict = await verify_studio_scene_delivery(\n                payload.provider,\n                messages,\n                text,\n                heat_level=heat,\n                verifier_context=context_text,\n            )\n            if verdict.get("verified") is not True:\n                text = pre_refine\n                if on_status is not None:\n                    await on_status("Craft Pass failed Studio delivery verification · preserving verified draft…")\n        refined = True\n'''
if text.count(quality_tail) < 2:
    raise RuntimeError("Expected quality refined markers")
text = text.replace(quality_tail, replacement, 1)
# Stream producer has no optional on_status variable; use emit_status in its copy.
replacement_stream = '''        if _is_studio_request(payload):\n            verdict = await verify_studio_scene_delivery(\n                payload.provider,\n                messages,\n                text,\n                heat_level=heat,\n                verifier_context=context_text,\n            )\n            if verdict.get("verified") is not True:\n                text = pre_refine\n                await emit_status("Craft Pass failed Studio delivery verification · preserving verified draft…")\n        refined = True\n'''
text = text.replace(quality_tail, replacement_stream, 1)
write(path, text)
replace_once(
    path,
    '    async def partial_or_error(detail: str) -> None:\n        partial = "".join(streamed_parts).strip()\n',
    '    async def partial_or_error(detail: str, partial_override: str | None = None) -> None:\n        partial = (partial_override if partial_override is not None else "".join(streamed_parts)).strip()\n',
)
replace_once(
    path,
    '''    except TimeoutError:\n''',
    '''    except StudioDeliveryIncomplete as exc:\n        await partial_or_error(exc.reason, exc.partial_text)\n    except TimeoutError:\n''',
)

# 4) Craft: Inferno/Scorching outrank a generic slow-burn pacing choice when the author asks for the core event.
path = "backend/app/craft.py"
replace_once(
    path,
    '''    files: list[str] = []\n''',
    '''    if heat in {"scorching", "inferno"} and curve == "slow_burn":\n        lines.append(\n            "Priority override: slow burn controls cadence inside the requested scene; it must not postpone, "\n            "replace, or consume the requested explicit core event when the author's instruction asks for it directly."\n        )\n\n    files: list[str] = []\n''',
)

# 5) Studio frontend: backend owns completion; no cascade of four hidden requests; partial is never called complete.
path = "frontend/src/AIStudioWorkspace.tsx"
text = read(path)
text = text.replace("const AUTO_CONTINUATION_PASSES = 4\n", "", 1)
text = text.replace(
    "    'STUDIO CONTINUATION CONTRACT:',\n",
    "    'STUDIO SCENE DELIVERY CONTRACT:',\n    'STUDIO CONTINUATION CONTRACT:',\n",
    1,
)
old = '''      const merged = mergeContinuation(output, result.text)\n      setOutput(merged)\n      setContextFiles(result.context_files || [])\n      setStatus(`Scene continued without replacing prior prose · ${wordsIn(merged).toLocaleString()} total words`)\n'''
new = '''      const merged = mergeContinuation(output, result.text)\n      setOutput(merged)\n      setContextFiles(result.context_files || [])\n      if (result.partial) {\n        setStatus(`Partial continuation preserved · ${wordsIn(merged).toLocaleString()} total words · ${result.warning || 'Studio delivery verification did not pass yet'}`)\n      } else {\n        setStatus(`Scene continued without replacing prior prose · ${wordsIn(merged).toLocaleString()} total words`)\n      }\n'''
if old not in text:
    raise RuntimeError("continueCurrentScene patch anchor not found")
text = text.replace(old, new, 1)
start = text.index("        const sceneBrief = direction\n")
end_marker = "        return\n      }\n\n      const result = await requestGeneration(direction, modeCopy.mode)"
end = text.index(end_marker, start)
replacement = '''        const sceneBrief = direction\n        const targetWords = sceneWordFloor(sceneBrief, craft.heat_level)\n        const result = await requestGeneration(freshScenePrompt(sceneBrief), 'write')\n        const draft = result.text.trim()\n        const words = wordsIn(draft)\n\n        setOutput(draft)\n        setContextFiles(result.context_files || [])\n\n        if (result.partial) {\n          setStatus(`Partial draft preserved · ${words.toLocaleString()} words · ${result.warning || 'Studio delivery verification did not pass; use Continue this scene to resume from the exact final line'}`)\n        } else if (words < targetWords || looksAbrupt(draft)) {\n          setStatus(`Completion contract warning · ${words.toLocaleString()} words · backend returned without a verified complete scene`)\n        } else if (result.refined) {\n          setStatus(`Scene complete · Craft Pass applied · ${words.toLocaleString()} words`)\n        } else {\n          setStatus(`Scene complete · ${words.toLocaleString()} words`)\n        }\n        return\n      }\n'''
text = text[:start] + replacement + text[end + len("        return\n      }\n"):]
write(path, text)

# 6) Acceptance tests: these are kept permanently as the gate for the exact regressions we observed.
test_path = ROOT / "backend/tests/test_studio_end_to_end_acceptance.py"
test_path.write_text(r'''from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app import craft, generation, routes_generation, storage, streaming_generation, studio_context
from app.models import CraftControls, GenerateRequest, ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + "."


def test_studio_continue_has_a_continuation_boundary_and_keeps_hard_canon_early(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Studio Acceptance")
    slug = project["slug"]
    storage.save_text(slug, "summaries/rolling-summary.md", "SUMMARY " * 7000)
    storage.save_text(slug, "characters/rowan.md", "# Rowan\n\nAdult Nexus. Attentive and protective.\n")
    storage.save_text(
        slug,
        "characters/avery.md",
        "# Avery\n\nAdult trans woman. Warm, playful, musical.\n" + ("canon filler " * 500) + "\nBODY_CANON_SENTINEL: explicit author body canon lives here.\n",
    )

    prompt = "Continue the Rowan and Avery Studio scene in the academy sauna."
    context, _, _, _ = studio_context.build_studio_context(
        slug,
        prompt,
        CraftControls(heat_level="inferno"),
        max_chars=36000,
        continuation=True,
    )

    assert "## Studio continuation boundary" in context
    assert "STUDIO SCENE DELIVERY CONTRACT:" in context
    assert "Requested Studio heat: inferno" in context
    assert "Start the requested prose from a NEW first line" not in context
    assert "BODY_CANON_SENTINEL" in context
    assert context.index("BODY_CANON_SENTINEL") < 20000


def test_fresh_studio_write_still_starts_new(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Fresh Studio Acceptance")
    slug = project["slug"]
    storage.save_text(slug, "characters/avery.md", "# Avery\n\nAdult character.\n")
    context, _, _, _ = studio_context.build_studio_context(
        slug,
        "Write a new scene with Avery.",
        CraftControls(heat_level="inferno"),
        continuation=False,
    )
    assert "## Fresh generation boundary" in context
    assert "Start the requested prose from a NEW first line" in context
    assert "Continue from the existing Studio draft" not in context


def test_studio_verifier_receives_heat_and_canon_on_continuation(monkeypatch) -> None:
    captured: dict[str, str] = {}
    raw = words("advance", 80) + "\n" + generation.SCENE_COMPLETE_MARKER

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        await on_delta(raw)
        return raw

    async def fake_verify(config, messages, draft, *, heat_level=None, verifier_context=""):
        captured["heat"] = heat_level or ""
        captured["context"] = verifier_context
        return {"verified": True, "canon_respected": True}

    async def emit(_text: str) -> None:
        return None

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verify)
    messages = generation.build_messages(
        "continue",
        "STUDIO CONTINUATION CONTRACT:\nContinue the existing Studio draft.",
        "Binder canon.",
        heat_level="inferno",
        min_scene_words=60,
    )
    result = asyncio.run(
        streaming_generation.generate_complete_prose_streamed(
            ProviderConfig(model="test-model"),
            messages,
            min_words=60,
            on_delta=emit,
            studio_scene=True,
            heat_level="inferno",
            verifier_context="BODY_CANON_SENTINEL",
        )
    )

    assert "advance0" in result
    assert captured == {"heat": "inferno", "context": "BODY_CANON_SENTINEL"}


def test_unverified_studio_scene_fails_closed_with_clean_partial(monkeypatch) -> None:
    calls = 0

    async def fake_stream(config, messages, *, on_delta, **kwargs):
        nonlocal calls
        calls += 1
        raw = words(f"attempt{calls}_", 90) + "\n" + generation.SCENE_COMPLETE_MARKER
        await on_delta(raw)
        return raw

    async def fake_verify(config, messages, draft, **kwargs):
        return {
            "verified": False,
            "canon_respected": True,
            "reason": "core encounter absent; buildup only",
        }

    async def emit(_text: str) -> None:
        return None

    monkeypatch.setattr(streaming_generation, "generate_streamed", fake_stream)
    monkeypatch.setattr(streaming_generation, "verify_studio_scene_delivery", fake_verify)
    messages = generation.build_messages(
        "write",
        "STUDIO SCENE DELIVERY CONTRACT:\nWrite the requested adult scene.",
        "Binder canon.",
        heat_level="inferno",
        min_scene_words=60,
    )

    with pytest.raises(streaming_generation.StudioDeliveryIncomplete) as caught:
        asyncio.run(
            streaming_generation.generate_complete_prose_streamed(
                ProviderConfig(model="test-model"),
                messages,
                min_words=60,
                on_delta=emit,
                max_passes=2,
                studio_scene=True,
                heat_level="inferno",
            )
        )

    assert calls == 2
    assert "attempt1_0" in caught.value.partial_text
    assert "buildup only" in caught.value.reason


def test_sync_studio_api_uses_same_verified_engine(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Sync Studio")
    slug = project["slug"]
    called: dict[str, object] = {}

    async def fake_verified(config, messages, **kwargs):
        called.update(kwargs)
        return words("verified", 80)

    async def forbidden_legacy(*args, **kwargs):
        raise AssertionError("Studio must not bypass the verified streaming engine")

    monkeypatch.setattr(routes_generation, "generate_complete_prose_streamed", fake_verified)
    monkeypatch.setattr(routes_generation, "generate_complete_prose", forbidden_legacy)
    monkeypatch.setattr(routes_generation, "record_assistance_event", lambda *args, **kwargs: {"id": "acceptance"})

    payload = GenerateRequest(
        prompt="STUDIO SCENE DELIVERY CONTRACT:\nWrite a complete new scene.",
        mode="write",
        provider=ProviderConfig(model="test-model"),
        craft=CraftControls(heat_level="inferno"),
    )
    response = asyncio.run(routes_generation._generate_payload(slug, payload, streamed=False))

    assert response.text.startswith("verified0")
    assert called["studio_scene"] is True
    assert called["heat_level"] == "inferno"


def test_craft_pass_cannot_replace_verified_studio_draft_with_failed_delivery(monkeypatch, tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Craft Verification")
    slug = project["slug"]
    verified = words("verified", 500)

    async def fake_generated(config, messages, **kwargs):
        return verified

    async def fake_quality(*args, **kwargs):
        return words("sanitized", 500)

    async def fake_verify(config, messages, draft, **kwargs):
        return {"verified": draft == verified, "canon_respected": True}

    monkeypatch.setattr(routes_generation, "generate_complete_prose_streamed", fake_generated)
    monkeypatch.setattr(routes_generation, "quality_pass", fake_quality)
    monkeypatch.setattr(routes_generation, "verify_studio_scene_delivery", fake_verify)
    monkeypatch.setattr(routes_generation, "record_assistance_event", lambda *args, **kwargs: {"id": "acceptance"})

    payload = GenerateRequest(
        prompt="STUDIO SCENE DELIVERY CONTRACT:\nWrite a complete scene.",
        mode="write",
        provider=ProviderConfig(model="test-model"),
        craft=CraftControls(heat_level="inferno", quality_pass=True),
    )
    response = asyncio.run(routes_generation._generate_payload(slug, payload, streamed=False))
    assert response.text == verified


def test_slow_burn_cannot_override_inferno_delivery_contract(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Craft Priority")
    text, _ = craft.build_craft_context(
        project["slug"],
        CraftControls(heat_level="inferno", tension_curve="slow_burn"),
    )
    assert "must not postpone, replace, or consume the requested explicit core event" in text


def test_real_http_ollama_stream_boundary(monkeypatch) -> None:
    chunks = ["Alpha ", "beta ", "gamma."]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:
            return None

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            assert self.path == "/api/chat"
            assert body["stream"] is True
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for chunk in chunks:
                payload = json.dumps({"message": {"content": chunk}, "done": False}).encode() + b"\n"
                self.wfile.write(payload)
                self.wfile.flush()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def fake_installed(_base_url: str):
        return ["test-model"]

    monkeypatch.setattr(streaming_generation, "installed_ollama_models", fake_installed)
    visible: list[str] = []

    async def emit(text: str) -> None:
        visible.append(text)

    try:
        result = asyncio.run(
            streaming_generation.generate_streamed(
                ProviderConfig(
                    provider="ollama",
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    model="test-model",
                ),
                [{"role": "user", "content": "test"}],
                on_delta=emit,
                max_output_tokens=128,
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result == "Alpha beta gamma."
    assert "".join(visible) == result


def test_frontend_does_not_launch_hidden_auto_continuation_cascade() -> None:
    source = (Path(__file__).resolve().parents[2] / "frontend/src/AIStudioWorkspace.tsx").read_text(encoding="utf-8")
    assert "AUTO_CONTINUATION_PASSES" not in source
    assert "if (result.partial)" in source
    assert "STUDIO SCENE DELIVERY CONTRACT:" in source
''', encoding="utf-8")

# 7) Dedicated acceptance workflow: a clean runner checks out the repo and exercises the exact Studio gate.
workflow = ROOT / ".github/workflows/studio-acceptance.yml"
workflow.write_text('''name: Studio Acceptance\n\non:\n  pull_request:\n    paths:\n      - "backend/app/generation.py"\n      - "backend/app/streaming_generation.py"\n      - "backend/app/routes_generation.py"\n      - "backend/app/studio_context.py"\n      - "backend/app/craft.py"\n      - "frontend/src/AIStudioWorkspace.tsx"\n      - "frontend/src/GenerationWatchdog.tsx"\n      - "backend/tests/test_studio_end_to_end_acceptance.py"\n      - ".github/workflows/studio-acceptance.yml"\n  workflow_dispatch:\n\njobs:\n  acceptance:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v7\n      - uses: actions/setup-python@v7\n        with:\n          python-version: "3.11"\n      - run: python -m pip install --upgrade pip setuptools\n      - run: python -m pip install -e "./backend[dev]"\n      - name: Run Studio end-to-end acceptance suite\n        run: pytest backend/tests/test_studio_end_to_end_acceptance.py -q\n      - name: Lint Studio acceptance paths\n        run: ruff check backend/app/streaming_generation.py backend/app/routes_generation.py backend/app/studio_context.py backend/app/craft.py backend/tests/test_studio_end_to_end_acceptance.py\n      - uses: actions/setup-node@v7\n        with:\n          node-version: "22"\n          cache: npm\n          cache-dependency-path: frontend/package-lock.json\n      - run: npm ci\n        working-directory: frontend\n      - name: Build production Studio frontend\n        run: npm run build\n        working-directory: frontend\n        env:\n          VITE_API_BASE_URL: https://api.example.invalid/api\n''', encoding="utf-8")

print("Studio acceptance patch prepared.")
