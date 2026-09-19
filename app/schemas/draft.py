from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DraftImageOut(BaseModel):
    img_key: str
    storage_path: str

    class Config:
        from_attributes = True


class DraftSessionDocOut(BaseModel):
    id: str
    role: str
    category: str
    original_filename: str
    storage_path: str

    class Config:
        from_attributes = True


class DraftCreate(BaseModel):
    name: str
    field_data: dict[str, Any] = {}
    linked_profiles: dict[str, str] = {}


class DraftUpdate(BaseModel):
    name: str | None = None
    field_data: dict[str, Any] | None = None
    linked_profiles: dict[str, str] | None = None


class DraftOut(BaseModel):
    id: str
    name: str
    field_data: dict[str, Any]
    linked_profiles: dict[str, str]
    employer_pdf_path: str
    created_at: datetime
    updated_at: datetime
    images: list[DraftImageOut] = []
    session_docs: list[DraftSessionDocOut] = []

    class Config:
        from_attributes = True


class DraftSummary(BaseModel):
    id: str
    name: str
    updated_at: datetime

    class Config:
        from_attributes = True
