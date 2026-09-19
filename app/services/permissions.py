"""Per-client feature gates: Lead Partner is always available; First/Second
Partner and signature/stamp uploads are granted per-user by an admin."""

from fastapi import HTTPException

from app.core.constants import role_of_prefixed_key
from app.models.user import User


def check_role_permission(user: User, role: str) -> None:
    if role == "lead":
        return
    if role == "first" and not user.can_use_first_partner:
        raise HTTPException(status_code=403, detail="First Partner access has not been enabled for your account.")
    if role == "second" and not user.can_use_second_partner:
        raise HTTPException(status_code=403, detail="Second Partner access has not been enabled for your account.")


def check_signature_upload_permission(user: User) -> None:
    if not user.can_upload_signature_stamp:
        raise HTTPException(
            status_code=403, detail="Signature/stamp upload has not been enabled for your account."
        )


def check_field_data_permission(user: User, field_data: dict) -> None:
    """Reject attempts to set non-empty values on a role's fields the user
    doesn't have access to — closes the direct-API-call bypass around the
    hidden tabs, not just the UI."""
    for key, value in field_data.items():
        if not value:
            continue
        role = role_of_prefixed_key(key)
        if role:
            check_role_permission(user, role)
