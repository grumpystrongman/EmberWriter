"""Exercise an isolated, writer-only installed backend without any local AI.

Designed to run *inside* a freshly extracted install with EMBER_DATA_DIR set
to a unique test-only folder outside the app code. Does not access author files.
This is not an OS-fresh or actual Pinokio-internal launcher certification.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from docx import Document
from ebooklib import epub
from fastapi.testclient import TestClient

from app import publishing, storage
from app.main import app

MARKER = "SYNTHETIC_OFFLINE_WRITER_QA_NO_CUSTOMER_DATA"


def run() -> dict:
    data = Path(os.environ["EMBER_DATA_DIR"]).resolve()
    assert "QA" in data.name and " " in str(data), "Only isolated QA folders are permitted"
    assert storage.PROJECTS_ROOT.resolve().parent == data

    manuscript = (
        "# The Quiet Engine\n\n"
        "The captain opened the lantern house and watched the old stars return.\n\n"
        + (MARKER + " The sky belonged to the characters, not the machine.\n\n") * 10
    )
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        result = client.post("/api/projects", json={
            "name": "Synthetic Fresh Install QA", "description": "No AI and no author data"
        })
        assert result.status_code == 200, result.text
        slug = result.json()["slug"]
        path = "manuscript/chapter-001.md"
        changed = client.put(f"/api/projects/{slug}/file", params={"path": path},
                             json={"content": manuscript})
        assert changed.status_code == 200, changed.text
        saved = client.get(f"/api/projects/{slug}/file", params={"path": path})
        assert saved.status_code == 200
        assert saved.json()["content"] == manuscript
        assert client.get(f"/api/projects/{slug}").status_code == 200
        assert client.get("/openapi.json").status_code == 200
        backups = client.post("/api/recovery/backup", json={"reason": "writer-only install QA"})
        assert backups.status_code == 201, backups.text
        generation = backups.json()["id"]
        verified = client.post(f"/api/recovery/generations/{generation}/verify")
        assert verified.status_code == 200
        assert verified.json()["healthy"]
        restored = client.post(f"/api/recovery/generations/{generation}/restore",
                               json={"confirmed": True})
        assert restored.status_code == 201, restored.text
        recovered_root = Path(restored.json()["directory"])
        restored_text = (recovered_root / "projects" / slug / path).read_text(encoding="utf-8")
        assert restored_text == manuscript
        assert client.get(f"/api/projects/{slug}/file",
                          params={"path": path}).json()["content"] == manuscript

    chapters = publishing.compiled_documents(slug)
    assert len(chapters) == 1
    export_dir = data / "QA exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    epub_file = export_dir / "qa-novel.epub"
    docx_file = export_dir / "qa-novel.docx"
    publishing.export_epub(epub_file, title="QA Title", author="QA Fixture",
                           language="en", documents=chapters, include_toc=True)
    publishing.export_docx(docx_file, title="QA Title", author="QA Fixture",
                           documents=chapters)
    assert any(MARKER in item.get_content().decode("utf-8")
               for item in epub.read_epub(str(epub_file)).get_items())
    assert MARKER in "\n".join(p.text for p in Document(docx_file).paragraphs)

    # Reopen after TestClient lifespan shutdown: the actual durable manuscript
    # file must still be available without loading the optional AI model.
    with TestClient(app) as client:
        again = client.get(f"/api/projects/{slug}/file", params={"path": path})
        assert again.status_code == 200 and again.json()["content"] == manuscript

    report = {
        "scenario": "same-host extracted writer-only install with spaces in path",
        "synthetic": True,
        "reused_developer_machine": True,
        "fresh_windows_machine": False,
        "pinokio_launcher_runtime_tested": False,
        "writer_without_ai": True,
        "api_create_save_reopen": True,
        "epub_export_sha256": hashlib.sha256(epub_file.read_bytes()).hexdigest(),
        "docx_export_sha256": hashlib.sha256(docx_file.read_bytes()).hexdigest(),
        "recovery_verified_and_restored": True,
        "manuscript_sha256": hashlib.sha256(manuscript.encode()).hexdigest(),
        "author_data_directory": str(data),
        "release_qualified": False,
    }
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
