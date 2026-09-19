"""Local-disk storage abstraction. Swappable for S3 later without touching callers."""

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
DEFAULT_EXTENSION = ".pdf"


def _root() -> Path:
    root = Path(settings.storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_EXTENSIONS else DEFAULT_EXTENSION


def save_upload(upload: UploadFile, *, subdir: str, stem: str | None = None) -> tuple[str, int]:
    """Persist an UploadFile under storage_root/subdir. Returns (relative_path, size_bytes)."""
    ext = _safe_extension(upload.filename or "")
    filename = f"{stem or uuid.uuid4().hex}{ext}"
    target_dir = _root() / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    size = 0
    with target_path.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            out.write(chunk)
    upload.file.close()

    return str(Path(subdir) / filename), size


def absolute_path(relative_path: str) -> Path:
    return _root() / relative_path


def delete(relative_path: str) -> None:
    path = absolute_path(relative_path)
    if path.exists():
        path.unlink()


def delete_dir(relative_dir: str) -> None:
    path = absolute_path(relative_dir)
    if path.exists():
        shutil.rmtree(path)
