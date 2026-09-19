from fastapi import APIRouter

from app.core.constants import ATTACHMENT_CATEGORIES, CATEGORY_LABELS, PARTNER_ROLE_LABELS, PARTNER_ROLES

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/constants")
def get_constants():
    return {
        "partner_roles": PARTNER_ROLES,
        "partner_role_labels": PARTNER_ROLE_LABELS,
        "attachment_categories": ATTACHMENT_CATEGORIES,
        "category_labels": CATEGORY_LABELS,
    }
