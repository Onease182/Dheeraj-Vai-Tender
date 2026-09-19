from typing import Any

from pydantic import BaseModel


class BidValidateRequest(BaseModel):
    field_data: dict[str, Any]
    authorized_signature_present: bool = False


class BidValidateResponse(BaseModel):
    is_ready: bool
    errors: list[str]
    percentage_total: float
