"""Extract plain text from uploaded office/document bytes for classification."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def extract_text(filename: str, data: bytes) -> str:
    """Best-effort text extraction. Never raises for unknown types."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}:
        return data.decode("utf-8", errors="replace")
    if suffix in {".doc", ".rtf", ".odt", ".xlsx", ".xls", ".pptx", ".ppt"}:
        # Binary office formats without a dedicated extractor: keep a
        # latin-1 lossy decode so keyword rules can still fire on strings.
        return data.decode("latin-1", errors="ignore")
    if suffix == ".pdf":
        return _extract_or_degrade(_from_pdf, data, filename)
    if suffix == ".docx":
        return _extract_or_degrade(_from_docx, data, filename)
    return data.decode("utf-8", errors="replace")


def _extract_or_degrade(
    extractor: Callable[[bytes], str], data: bytes, filename: str
) -> str:
    """Run a format extractor, degrading to a lossy decode on any parse failure.

    The extractor libraries (pypdf, python-docx) raise a wide, version-unstable
    set of exceptions on malformed or truncated uploads, so this stays a
    best-effort boundary that never raises. It logs the failure with the
    exception so a corrupt document silently decoded into the classifier is
    observable rather than an invisible degradation.
    """
    try:
        return extractor(data)
    except Exception:
        logger.warning(
            "Text extraction failed for %r; falling back to a lossy utf-8 "
            "decode, so the classifier will see degraded text.",
            filename,
            exc_info=True,
        )
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
