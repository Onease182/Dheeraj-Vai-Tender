from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_admin: bool
    email_verified: bool
    trial_ends_at: datetime
    trial_expired: bool
    created_at: datetime
    generation_count: int = 0
    can_use_first_partner: bool
    can_use_second_partner: bool
    can_upload_signature_stamp: bool
    subscription_amount: float | None = None
    subscription_duration_days: int | None = None

    class Config:
        from_attributes = True


class AdminGeneratedDocumentOut(BaseModel):
    id: str
    doc_id: str
    filename: str
    jv_name: str
    partner_count: int
    created_at: datetime
    download_url: str


class AdminGenerationHistoryResponse(BaseModel):
    total: int
    items: list[AdminGeneratedDocumentOut]


class AdminUserUpdate(BaseModel):
    is_admin: bool | None = None
    email_verified: bool | None = None
    trial_ends_at: datetime | None = None
    extend_trial_days: int | None = None  # convenience: add N days to current trial_ends_at
    can_use_first_partner: bool | None = None
    can_use_second_partner: bool | None = None
    can_upload_signature_stamp: bool | None = None
    subscription_amount: float | None = None
    subscription_duration_days: int | None = None


class AdminDraftSummary(BaseModel):
    id: str
    name: str
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminDraftImageOut(BaseModel):
    img_key: str
    storage_path: str

    class Config:
        from_attributes = True


class AdminDraftSessionDocOut(BaseModel):
    id: str
    role: str
    category: str
    original_filename: str

    class Config:
        from_attributes = True


class AdminDraftOut(BaseModel):
    id: str
    name: str
    field_data: dict[str, Any]
    updated_at: datetime
    images: list[AdminDraftImageOut] = []
    session_docs: list[AdminDraftSessionDocOut] = []

    class Config:
        from_attributes = True


class AdminDraftUpdate(BaseModel):
    name: str | None = None
    field_data: dict[str, Any] | None = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str | None = None  # omit to auto-generate a random password


class AdminResetPasswordResponse(BaseModel):
    new_password: str


class AdminGenerateRequest(BaseModel):
    draft_id: str


class AdminGenerateResponse(BaseModel):
    id: str
    filename: str
    download_url: str
