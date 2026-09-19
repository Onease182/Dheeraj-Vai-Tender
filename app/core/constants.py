"""Ported from the desktop app's profiles.py — shared domain constants."""

PARTNER_ROLES = ["lead", "first", "second"]

PARTNER_ROLE_LABELS = {
    "lead": "Lead Partner",
    "first": "First Partner",
    "second": "Second Partner",
}

ROLE_PREFIXES = {"lead": "LEAD", "first": "FIRST", "second": "SECOND"}
PERCENTAGE_KEYS = {"lead": "L_PER", "first": "F_PER", "second": "S_PER"}

ATTACHMENT_CATEGORIES = [
    "experience",
    "registration",
    "audits",
    "bank_guarantee",
    "line_of_credit",
]

CATEGORY_LABELS = {
    "experience": "Experience Letters",
    "registration": "Registration & Legal Documents",
    "audits": "Audit Documents & Financial Statements",
    "bank_guarantee": "Bank Guarantee Documents",
    "line_of_credit": "Line of Credit",
}


def role_image_keys(role: str) -> list[str]:
    prefix = ROLE_PREFIXES[role]
    return [f"{prefix}_CEO_SIG", f"{prefix}_STAMP", f"{prefix}_PARTNER_MD1", f"{prefix}_PARTNER_MD2"]


def role_of_prefixed_key(key: str) -> str | None:
    """LEAD_PARTNER_NAME -> 'lead', FIRST_CEO_SIG -> 'first', etc. None if
    the key isn't role-prefixed (e.g. PROJECT_NAME, JV_NAME)."""
    for role, prefix in ROLE_PREFIXES.items():
        if key.startswith(f"{prefix}_"):
            return role
    return None
