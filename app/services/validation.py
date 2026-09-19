"""Single source of truth for bid validation — replaces the 3 duplicated
percentage/readiness checks scattered across the desktop app's app.py
(_validate_bid, generate_doc, _update_percentage_total)."""

from app.core.constants import PERCENTAGE_KEYS


def _parse_percentage(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return float(str(raw).replace("%", "").strip())
    except ValueError:
        return 0.0


def percentage_total(field_data: dict) -> float:
    is_single = field_data.get("BID_TYPE") == "Single Bidder"
    if is_single:
        return _parse_percentage(field_data.get(PERCENTAGE_KEYS["lead"], "0"))

    has_first = bool(field_data.get("FIRST_PARTNER_NAME"))
    has_second = bool(field_data.get("SECOND_PARTNER_NAME"))

    total = _parse_percentage(field_data.get(PERCENTAGE_KEYS["lead"], "0"))
    if has_first:
        total += _parse_percentage(field_data.get(PERCENTAGE_KEYS["first"], "0"))
    if has_second:
        total += _parse_percentage(field_data.get(PERCENTAGE_KEYS["second"], "0"))
    return round(total, 2)


def is_split_valid(field_data: dict) -> bool:
    return abs(percentage_total(field_data) - 100.0) < 0.01


class BidValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def determine_partner_count(field_data: dict) -> int:
    is_single = field_data.get("BID_TYPE") == "Single Bidder"
    if is_single:
        if not field_data.get("LEAD_PARTNER_NAME"):
            raise BidValidationError(["Lead partner name is required."])
        return 1

    if not field_data.get("LEAD_PARTNER_NAME"):
        raise BidValidationError(["Lead partner name is required."])

    has_first = bool(field_data.get("FIRST_PARTNER_NAME"))
    has_second = bool(field_data.get("SECOND_PARTNER_NAME"))

    if has_second and not has_first:
        raise BidValidationError(["First partner must be filled before Second partner."])

    if has_second:
        return 3
    if has_first:
        return 2
    return 1


def validate_bid(field_data: dict, *, authorized_signature_present: bool) -> list[str]:
    """Returns a list of validation error messages (empty = ready to generate)."""
    errors: list[str] = []

    try:
        determine_partner_count(field_data)
    except BidValidationError as exc:
        errors.extend(exc.errors)

    if not field_data.get("PROJECT_NAME"):
        errors.append("Project name is required.")
    if not field_data.get("EMPLOYER_NAME"):
        errors.append("Employer name is required.")
    if not is_split_valid(field_data):
        errors.append(f"Ownership split must total 100% (currently {percentage_total(field_data)}%).")
    if not authorized_signature_present:
        errors.append("Authorized person's signature is required.")

    return errors
