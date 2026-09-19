from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    draft_id: str
    field_data: dict[str, Any]


class GenerateResponse(BaseModel):
    id: str
    filename: str
    download_url: str


class GeneratedDocumentOut(BaseModel):
    id: str
    doc_id: str
    filename: str
    jv_name: str
    partner_count: int
    created_at: datetime
    download_url: str

    class Config:
        from_attributes = True


class GenerationHistoryResponse(BaseModel):
    total: int
    items: list[GeneratedDocumentOut]
