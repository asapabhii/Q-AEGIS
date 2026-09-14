"""Local-disk document storage helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.config import get_settings


def storage_root() -> Path:
    """Absolute storage directory for uploaded bytes."""
    root = Path(get_settings().document_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_upload(*, document_id: UUID, filename: str, data: bytes) -> str:
    """Write bytes and return ``storage_path`` relative to the storage root."""
    safe_name = Path(filename).name.replace("..", "_") or "upload.bin"
    folder = storage_root() / str(document_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name
    path.write_bytes(data)
    return f"{document_id}/{safe_name}"
