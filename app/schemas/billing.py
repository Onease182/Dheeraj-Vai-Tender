from datetime import datetime

from pydantic import BaseModel


class InvoiceOut(BaseModel):
    id: str
    user_id: str
    amount: float
    duration_days: int
    status: str
    proof_image_path: str | None = None
    proof_reference: str | None = None
    notes: str
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CurrentInvoiceResponse(BaseModel):
    locked: bool
    invoice: InvoiceOut | None = None
    qr_code_available: bool = False
    message: str | None = None  # set when locked but no invoice can be generated (no price configured yet)


class SubmitProofRequest(BaseModel):
    proof_reference: str = ""


class AdminInvoiceCreate(BaseModel):
    amount: float
    duration_days: int
    status: str = "pending"
    notes: str = ""


class AdminInvoiceUpdate(BaseModel):
    amount: float | None = None
    duration_days: int | None = None
    status: str | None = None
    notes: str | None = None
