"""Extract plain text from uploaded office/document bytes for classification."""

from __future__ import annotations

import io
from pathlib import Path


def extract_text(filename: str, data: bytes) -> str:
    """Best-effort text extraction. Never raises for unknown types."""
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}:
            return data.decode("utf-8", errors="replace")
        if suffix == ".pdf":
            return _from_pdf(data)
        if suffix in {".docx"}:
            return _from_docx(data)
        if suffix in {".doc", ".rtf", ".odt", ".xlsx", ".xls", ".pptx", ".ppt"}:
            # Binary office formats without a dedicated extractor: keep a
            # latin-1 lossy decode so keyword rules can still fire on strings.
            return data.decode("latin-1", errors="ignore")
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _from_docx(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)
