from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Page:
    text: str
    page_number: int


def parse_pdf(path: Path) -> list[Page]:
    import pdfplumber

    pages: list[Page] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            # pdfplumber peut retourner None pour page image
            pages.append(Page(text=txt, page_number=i))

    if not pages:
        raise ValueError("PDF scanné non supporté")

    total = sum(len(p.text) for p in pages)
    avg = total / len(pages) if pages else 0
    if avg < 50:
        raise ValueError("PDF scanné non supporté")

    return pages


def parse_txt(path: Path) -> list[Page]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [Page(text=text, page_number=1)]


def parse_md(path: Path) -> list[Page]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [Page(text=text, page_number=1)]


def parse_docx(path: Path) -> list[Page]:
    import docx  # python-docx

    document = docx.Document(str(path))
    text = "\n".join([p.text for p in document.paragraphs])
    return [Page(text=text, page_number=1)]


def parse(path: Path) -> list[Page]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".txt":
        return parse_txt(path)
    if ext == ".md":
        return parse_md(path)
    if ext == ".docx":
        return parse_docx(path)
    raise ValueError(f"Extension non supportée: {ext}")
