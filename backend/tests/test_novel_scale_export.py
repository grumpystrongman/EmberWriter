"""Synthetic full-novel export stress checks; no author manuscript is accessed."""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.publishing import export_epub


def test_epub_export_retains_order_and_navigation_at_novel_scale(tmp_path: Path):
    # 180 chapters, ~45,000 words: enough to catch truncation, naming
    # collisions, missing navigation, and early-chapter-only processing.
    documents = [
        {
            "title": f"Chapter {number:03d}",
            "content": (f"Unique opening for chapter {number:03d}. " + "A deliberate sentence of synthetic narrative. " * 40) * 6,
        }
        for number in range(1, 181)
    ]
    output = tmp_path / "stress-test.epub"
    export_epub(
        output, title="Synthetic Novel", author="Test Author",
        language="en", documents=documents, include_toc=True,
    )
    with zipfile.ZipFile(output) as book:
        assert book.testzip() is None
        names = book.namelist()
        chapters = sorted(name for name in names if name.endswith(".xhtml") and "chapter-" in name)
        assert len(chapters) == 180
        assert len(set(chapters)) == 180
        assert b"Unique opening for chapter 001" in book.read(chapters[0])
        assert b"Unique opening for chapter 180" in book.read(chapters[-1])
        assert any(name.endswith("nav.xhtml") for name in names)
        opf_name = next(name for name in names if name.endswith(".opf"))
        opf = ElementTree.fromstring(book.read(opf_name))
        assert any(element.tag.endswith("language") and element.text == "en" for element in opf.iter())
