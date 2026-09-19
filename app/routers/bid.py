from fastapi import APIRouter, Depends

from app.core.deps import get_verified_active_user
from app.models.user import User
from app.schemas.bid import BidValidateRequest, BidValidateResponse
from app.services.validation import percentage_total, validate_bid

router = APIRouter(prefix="/bid", tags=["bid"])


@router.post("/validate", response_model=BidValidateResponse)
def validate(payload: BidValidateRequest, user: User = Depends(get_verified_active_user)):
    errors = validate_bid(payload.field_data, authorized_signature_present=payload.authorized_signature_present)
    return BidValidateResponse(
        is_ready=not errors,
        errors=errors,
        percentage_total=percentage_total(payload.field_data),
    )
