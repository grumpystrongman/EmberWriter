from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from app import storage
from app.main import app

MODEL = "emberwriter-e2e-model:latest"
COMPLETE = "[[EMBER_SCENE_COMPLETE]]"


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{index}" for index in range(count)) + "."


class FakeOllamaState:
    def __init__(self) -> None:
        self.writer_calls: list[dict] = []
        self.verifier_calls: list[dict] = []


class FakeOllamaHandler(BaseHTTPRequestHandler):
    server_version = "EmberWriterFakeOllama/1.0"

    def log_message(self, *_args) -> None:  # pragma: no cover - keep test output clean
        return

    @property
    def state(self) -> FakeOllamaState:
        return self.server.state  # type: ignore[attr-defined]

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._json(200, {"models": [{"name": MODEL, "model": MODEL}]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        messages = payload.get("messages", [])
        system = str(messages[0].get("content", "")) if messages else ""
        is_verifier = "strict scene-delivery verifier" in system

        if is_verifier:
            self.state.verifier_calls.append(payload)
            draft = str(messages[-1].get("content", "")) if messages else ""
            force_reject = "NEVER_VERIFY" in draft
            delivered = (not force_reject) and all(
                marker in draft
                for marker in (
                    "CORE_EVENT_DELIVERED",
                    "AFTERMATH_LANDED",
                    "MUNA_BODY_CANON_OK",
                )
            )
            verdict = {
                "core_encounter_on_page": delivered,
                "requested_explicitness_delivered": delivered,
                "buildup_only": not delivered,
                "fade_or_skip": False,
                "ending_complete": delivered,
                "canon_respected": "CANON_VIOLATION" not in draft,
                "repetition_loop": False,
                "reason": (
                    "forced verifier rejection for E2E safety test"
                    if force_reject
                    else "core event and aftermath present"
                    if delivered
                    else "buildup only; requested core event absent"
                ),
            }
            self._json(200, {"message": {"content": json.dumps(verdict)}, "done": True})
            return

        self.state.writer_calls.append(payload)
        call_index = len(self.state.writer_calls)
        all_text = "\n".join(str(message.get("content", "")) for message in messages)
        is_continuation = (
            "Continue the SAME scene" in all_text
            or "STUDIO CONTINUATION CONTRACT:" in all_text
            or any(message.get("role") == "assistant" for message in messages)
        )

        if call_index == 1 and not is_continuation:
            prose = _words("BUILDUP_ONLY", 930) + "\n" + COMPLETE
        else:
            prose = (
                _words("NEW_BEAT", 420)
                + " CORE_EVENT_DELIVERED MUNA_BODY_CANON_OK AFTERMATH_LANDED.\n"
                + COMPLETE
            )

        if not payload.get("stream"):
            self._json(200, {"message": {"content": prose}, "done": True})
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for index in range(0, len(prose), 240):
            line = json.dumps({"message": {"content": prose[index:index + 240]}, "done": False})
            self.wfile.write((line + "\n").encode("utf-8"))
            self.wfile.flush()
        self.wfile.write((json.dumps({"message": {"content": ""}, "done": True}) + "\n").encode("utf-8"))
        self.wfile.flush()


def _start_fake_ollama() -> tuple[ThreadingHTTPServer, FakeOllamaState, str]:
    state = FakeOllamaState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
    server.state = state  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, state, f"http://{host}:{port}"


def _setup_project(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    project = storage.create_project("Studio Contract E2E")
    slug = project["slug"]

    storage.save_text(
        slug,
        "manuscript/chapter-001.md",
        "WRONG_JAX_CHAPTER " + ("Kaelen academy gym battle Jax " * 800),
    )
    storage.save_text(
        slug,
        "characters/kaelen.md",
        "# Kaelen\n\nAdult Nexus. Attentive, protective, emotionally responsive.\n",
    )
    storage.save_text(
        slug,
        "characters/muna.md",
        "# Muna\n\nAdult trans woman. Warm, playful, musical, joyful.\n\n"
        + ("Character history and voice detail. " * 210)
        + "\n\nHARD EMBODIMENT CANON: MUNA_BODY_CANON_OK. Do not invent conflicting anatomy.\n",
    )
    storage.save_text(
        slug,
        "world/aethelgard-academy.md",
        "# Aethelgard Academy\n\nThe academy gym includes a private sauna used after training.\n",
    )
    return slug


def _payload(base_url: str, prompt: str, mode: str = "write") -> dict:
    return {
        "prompt": prompt,
        "mode": mode,
        "active_file": None,
        "selected_text": "__EMBER_STUDIO_CONTEXT_V1__",
        "provider": {
            "provider": "ollama",
            "base_url": base_url,
            "model": MODEL,
            "api_key": None,
        },
        "craft": {
            "heat_level": "inferno",
            "tension_curve": "flashpoint",
            "voice_lock": True,
            "quality_pass": False,
            "sensory_intensity": 4,
            "dialogue_intensity": 3,
            "interiority": 4,
        },
    }


def _stream_final(client: TestClient, slug: str, payload: dict) -> tuple[list[dict], dict]:
    events: list[dict] = []
    with client.stream("POST", f"/api/projects/{slug}/generate/stream", json=payload) as response:
        assert response.status_code == 200, response.text
        for line in response.iter_lines():
            if not line.strip():
                continue
            events.append(json.loads(line))
    finals = [event for event in events if event.get("type") == "final"]
    assert finals, events
    return events, finals[-1]


def test_studio_inferno_is_verified_end_to_end_on_clean_api_path(tmp_path: Path) -> None:
    server, state, base_url = _start_fake_ollama()
    try:
        slug = _setup_project(tmp_path)
        payload = _payload(
            base_url,
            (
                "Write a 900 word complete adult intimacy scene between Kaelen and Muna in the academy sauna. "
                "STUDIO SCENE DELIVERY CONTRACT: deliver the requested core event and aftermath, not just buildup."
            ),
        )

        with TestClient(app) as client:
            events, final = _stream_final(client, slug, payload)

        text = str(final["text"])
        assert final.get("partial") is False
        assert "CORE_EVENT_DELIVERED" in text
        assert "AFTERMATH_LANDED" in text
        assert "MUNA_BODY_CANON_OK" in text
        assert "WRONG_JAX_CHAPTER" not in text
        assert len(state.writer_calls) >= 2, "buildup-only first pass must be rejected and continued"
        assert len(state.verifier_calls) >= 2, "delivery verifier must reject buildup then approve delivered scene"
        assert any(event.get("message") == "Verifying requested scene delivery…" for event in events)
        assert any("Delivery check failed" in str(event.get("message", "")) for event in events)
        assert any("Requested scene delivery verified" in str(event.get("message", "")) for event in events)

        first_writer_context = "\n".join(
            str(message.get("content", "")) for message in state.writer_calls[0].get("messages", [])
        )
        assert "MUNA_BODY_CANON_OK" in first_writer_context
        assert "WRONG_JAX_CHAPTER" not in first_writer_context
        assert "Requested heat: inferno." in first_writer_context
    finally:
        server.shutdown()
        server.server_close()


def test_studio_continue_context_never_tells_model_to_start_over(tmp_path: Path) -> None:
    server, state, base_url = _start_fake_ollama()
    try:
        slug = _setup_project(tmp_path)
        handoff = "CURRENT_STUDIO_ENDING_SENTENCE."
        payload = _payload(
            base_url,
            (
                "Continue and finish the current 300 word scene.\n"
                "STUDIO CONTINUATION CONTRACT:\n"
                "Continue from the EXACT END below; never restart.\n"
                f"EXISTING DRAFT HANDOFF\n{handoff}\n"
                "WRITE ONLY NEW PROSE AFTER THAT FINAL LINE."
            ),
            mode="continue",
        )

        with TestClient(app) as client:
            _events, final = _stream_final(client, slug, payload)

        assert final.get("partial") is False
        sent = "\n".join(
            str(message.get("content", "")) for message in state.writer_calls[0].get("messages", [])
        )
        assert "CURRENT_STUDIO_ENDING_SENTENCE" in sent
        assert "## Studio continuation boundary" in sent
        assert "Start the requested prose from a NEW first line" not in sent
        assert "WRONG_JAX_CHAPTER" not in sent
        assert state.verifier_calls, "explicit Studio continuation must still pass the delivery verifier"
    finally:
        server.shutdown()
        server.server_close()


def test_unverified_studio_scene_can_never_be_reported_complete(tmp_path: Path) -> None:
    server, state, base_url = _start_fake_ollama()
    try:
        slug = _setup_project(tmp_path)
        payload = _payload(
            base_url,
            (
                "NEVER_VERIFY. Write a 900 word complete adult intimacy scene between Kaelen and Muna. "
                "STUDIO SCENE DELIVERY CONTRACT: do not report success unless the independent verifier approves."
            ),
        )

        with TestClient(app) as client:
            events, final = _stream_final(client, slug, payload)

        assert state.verifier_calls, "the verifier must actually run"
        assert final.get("partial") is True, (
            "a Studio intimacy draft that never passes the independent verifier must be partial, never complete"
        )
        assert final.get("warning"), events
        assert "verified" in str(final.get("warning", "")).casefold() or "delivery" in str(final.get("warning", "")).casefold()
    finally:
        server.shutdown()
        server.server_close()
