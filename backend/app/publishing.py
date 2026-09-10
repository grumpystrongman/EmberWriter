from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import markdown as markdown_lib
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches, Pt
from ebooklib import epub
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .binder import get_binder
from .storage import project_root, read_text


def _slug(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return result or "manuscript"


def _children(state, parent_id: str):
    return sorted(
        (node for node in state.nodes if node.parent_id == parent_id),
        key=lambda node: node.position,
    )


def compiled_documents(slug: str) -> list[dict]:
    state = get_binder(slug)
    node_map = {node.id: node for node in state.nodes}
    draft = next((node_map[node_id] for node_id in state.roots if node_map[node_id].title == "Draft"), None)
    if draft is None:
        raise ValueError("Binder Draft root is missing")

    result: list[dict] = []

    def visit(parent_id: str) -> None:
        for node in _children(state, parent_id):
            if node.kind == "folder":
                visit(node.id)
                continue
            if not node.include_in_compile or not node.path or node.custom_metadata.get("source_missing"):
                continue
            try:
                content = read_text(slug, node.path)
            except (FileNotFoundError, OSError, ValueError, UnicodeError):
                continue
            result.append(
                {
                    "id": node.id,
                    "title": node.title,
                    "path": node.path,
                    "content": content,
                    "word_count": node.word_count,
                    "metadata": node.custom_metadata,
                }
            )

    visit(draft.id)
    if not result:
        raise ValueError("No Binder documents are enabled for Compile")
    return result


def _markdown_html(content: str) -> str:
    return markdown_lib.markdown(content, extensions=["extra", "sane_lists"])


def _plain(content: str) -> str:
    return BeautifulSoup(_markdown_html(content), "html.parser").get_text("\n", strip=True)


def _clean_chapter_content(content: str, title: str) -> str:
    lines = content.splitlines()
    if lines and re.match(r"^#\s+", lines[0].strip()):
        heading = re.sub(r"^#\s+", "", lines[0].strip()).strip()
        if heading.casefold() == title.strip().casefold():
            return "\n".join(lines[1:]).lstrip()
    return content


def export_docx(path: Path, *, title: str, author: str, documents: list[dict]) -> None:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.8)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    title_para = doc.add_paragraph()
    title_para.alignment = 1
    title_run = title_para.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(22)
    if author:
        author_para = doc.add_paragraph()
        author_para.alignment = 1
        author_para.add_run(author).italic = True
    doc.add_page_break()

    for index, item in enumerate(documents):
        if index:
            doc.add_page_break()
        doc.add_heading(item["title"], level=1)
        body = _clean_chapter_content(item["content"], item["title"])
        soup = BeautifulSoup(_markdown_html(body), "html.parser")
        for element in soup.find_all(recursive=False):
            if element.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                doc.add_heading(element.get_text(" ", strip=True), level=min(3, int(element.name[1])))
            elif element.name in {"ul", "ol"}:
                style = "List Bullet" if element.name == "ul" else "List Number"
                for li in element.find_all("li", recursive=False):
                    doc.add_paragraph(li.get_text(" ", strip=True), style=style)
            elif element.name == "blockquote":
                paragraph = doc.add_paragraph(element.get_text(" ", strip=True))
                paragraph.paragraph_format.left_indent = Inches(0.35)
            else:
                text = element.get_text(" ", strip=True)
                if text:
                    doc.add_paragraph(text)
    doc.save(path)


def export_epub(
    path: Path,
    *,
    title: str,
    author: str,
    language: str,
    documents: list[dict],
    include_toc: bool,
) -> None:
    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid4()}")
    book.set_title(title)
    book.set_language(language or "en")
    if author:
        book.add_author(author)

    chapters = []
    for index, item in enumerate(documents, start=1):
        filename = f"chapter-{index:04d}.xhtml"
        chapter = epub.EpubHtml(title=item["title"], file_name=filename, lang=language or "en")
        body = _clean_chapter_content(item["content"], item["title"])
        chapter.content = (
            f"<h1>{html.escape(item['title'])}</h1>\n" + _markdown_html(body)
        ).encode("utf-8")
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters) if include_toc else ()
    book.spine = ["nav", *chapters]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    style = "body { font-family: serif; line-height: 1.45; } h1 { text-align: center; margin: 2em 0; }"
    css = epub.EpubItem(uid="style", file_name="style/book.css", media_type="text/css", content=style)
    book.add_item(css)
    for chapter in chapters:
        chapter.add_item(css)
    epub.write_epub(str(path), book)


def export_pdf(
    path: Path,
    *,
    title: str,
    author: str,
    documents: list[dict],
    trim_width: float,
    trim_height: float,
) -> None:
    page_size = (trim_width * inch, trim_height * inch)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=page_size,
        rightMargin=0.7 * inch,
        leftMargin=0.9 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=title,
        author=author,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "BookBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=14,
        spaceAfter=7,
        firstLineIndent=16,
        allowWidows=0,
        allowOrphans=0,
    )
    chapter_style = ParagraphStyle(
        "ChapterTitle",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=28,
    )
    title_style = ParagraphStyle(
        "BookTitle",
        parent=chapter_style,
        fontSize=24,
        leading=30,
        spaceBefore=1.8 * inch,
    )
    story = [Paragraph(html.escape(title), title_style)]
    if author:
        story.extend([Spacer(1, 0.25 * inch), Paragraph(html.escape(author), chapter_style)])
    story.append(PageBreak())

    for index, item in enumerate(documents):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(html.escape(item["title"]), chapter_style))
        plain = _plain(_clean_chapter_content(item["content"], item["title"]))
        for paragraph in re.split(r"\n\s*\n|\n", plain):
            paragraph = paragraph.strip()
            if paragraph:
                story.append(Paragraph(html.escape(paragraph), body))
    doc.build(story)


def export_project(
    slug: str,
    *,
    formats: list[str],
    title: str,
    author: str = "",
    language: str = "en",
    include_toc: bool = True,
    trim_width: float = 6.0,
    trim_height: float = 9.0,
) -> dict:
    allowed = {"docx", "epub", "pdf"}
    normalized = []
    for item in formats:
        value = item.casefold().strip().lstrip(".")
        if value not in allowed:
            raise ValueError(f"Unsupported publish format: {item}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        raise ValueError("Choose at least one publish format")
    if not 4.0 <= trim_width <= 8.5 or not 6.0 <= trim_height <= 11.7:
        raise ValueError("Print trim size is outside supported book dimensions")

    documents = compiled_documents(slug)
    export_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    directory = project_root(slug) / "exports" / export_id
    directory.mkdir(parents=True, exist_ok=True)
    base = _slug(title)
    artifacts = []

    for fmt in normalized:
        path = directory / f"{base}.{fmt}"
        if fmt == "docx":
            export_docx(path, title=title, author=author, documents=documents)
        elif fmt == "epub":
            export_epub(
                path,
                title=title,
                author=author,
                language=language,
                documents=documents,
                include_toc=include_toc,
            )
        else:
            export_pdf(
                path,
                title=title,
                author=author,
                documents=documents,
                trim_width=trim_width,
                trim_height=trim_height,
            )
        artifacts.append(
            {
                "format": fmt,
                "filename": path.name,
                "relative_path": str(path.relative_to(project_root(slug))).replace("\\", "/"),
                "bytes": path.stat().st_size,
            }
        )

    return {
        "export_id": export_id,
        "title": title,
        "documents": len(documents),
        "words": sum(item["word_count"] for item in documents),
        "artifacts": artifacts,
    }
