from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TenderOut(BaseModel):
    id: str
    title: str
    organization: str
    category: Optional[str]
    district: Optional[str]
    budget: Optional[str]
    description: Optional[str]
    source: str
    source_url: Optional[str]
    newspaper_name: Optional[str]
    publication_date: Optional[datetime]
    submission_deadline: Optional[datetime]
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenderList(BaseModel):
    items: list[TenderOut]
    total: int
    page: int
    page_size: int
    pages: int
