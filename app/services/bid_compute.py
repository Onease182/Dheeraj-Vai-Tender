"""Derived fields added at generation time — ported from app.py's generate_doc()."""

from app.services.validation import BidValidationError, determine_partner_count


def with_derived_fields(field_data: dict) -> dict:
    data = dict(field_data)
    is_jv = data.get("BID_TYPE") != "Single Bidder"
    data["AND_CONNECTOR"] = "And" if is_jv else ""
    data["HAS_THIRD_PARTNER"] = "True" if data.get("SECOND_PARTNER_NAME") else "False"
    data["AUTHORIZED_CAPACITY"] = "Authorised person of JV"
    data.setdefault("BID_TYPE", "Joint Venture")
    return data


def resolve_authorized_signature_key(field_data: dict) -> str | None:
    """AUTHORISED_SIG aliases whichever partner CEO signature matches the
    selected AUTHORIZED_PERSON_NAME."""
    authorized_name = field_data.get("AUTHORIZED_PERSON_NAME")
    if not authorized_name:
        return None
    for prefix in ("LEAD", "FIRST", "SECOND"):
        if field_data.get(f"{prefix}_PARTNER_CEO") == authorized_name:
            return f"{prefix}_CEO_SIG"
    return None


__all__ = ["with_derived_fields", "resolve_authorized_signature_key", "determine_partner_count", "BidValidationError"]
