from datetime import datetime

from pydantic import BaseModel


class ProfileImageOut(BaseModel):
    img_key: str
    storage_path: str

    class Config:
        from_attributes = True


class ProfileAttachmentOut(BaseModel):
    id: str
    category: str
    original_filename: str
    storage_path: str
    file_size: int
    description: str

    class Config:
        from_attributes = True


class ProfileCreate(BaseModel):
    name: str
    role: str
    partner_name: str = ""
    partner_short: str = ""
    address: str = ""
    partner_ceo: str = ""
    partner_md1: str = ""
    partner_md2: str = ""


class ProfileUpdate(BaseModel):
    name: str | None = None
    partner_name: str | None = None
    partner_short: str | None = None
    address: str | None = None
    partner_ceo: str | None = None
    partner_md1: str | None = None
    partner_md2: str | None = None


class ProfileOut(BaseModel):
    id: str
    name: str
    role: str
    partner_name: str
    partner_short: str
    address: str
    partner_ceo: str
    partner_md1: str
    partner_md2: str
    created_at: datetime
    updated_at: datetime
    images: list[ProfileImageOut] = []
    attachments: list[ProfileAttachmentOut] = []

    class Config:
        from_attributes = True


class ProfileSummary(BaseModel):
    id: str
    name: str
    role: str
    partner_name: str
    updated_at: datetime

    class Config:
        from_attributes = True
