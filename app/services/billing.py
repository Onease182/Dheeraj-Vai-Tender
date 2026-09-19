"""Manual/offline subscription billing: admin sets a per-user price +
duration, the user pays via a QR code outside the app and submits proof,
admin verifies and the user's access is extended by that invoice's duration.

No payment gateway integration — this is intentionally a manual reconciliation
flow, matching a QR-based offline payment model."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.user import User

ACTIVE_STATUSES = ("pending", "submitted", "rejected")


def get_or_create_current_invoice(db: Session, user: User) -> Invoice | None:
    """Returns the invoice the locked user should be looking at right now,
    creating one if this is a fresh billing cycle and the admin has set a
    price for them. Returns None if the user isn't locked, or if no price
    has been configured yet (nothing to invoice)."""
    if not user.trial_expired:
        return None

    existing = (
        db.query(Invoice)
        .filter(Invoice.user_id == user.id, Invoice.status.in_(ACTIVE_STATUSES))
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if existing:
        return existing

    if user.subscription_amount is None or user.subscription_duration_days is None:
        return None

    invoice = Invoice(
        user_id=user.id,
        amount=user.subscription_amount,
        duration_days=user.subscription_duration_days,
        status="pending",
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def verify_invoice(db: Session, invoice: Invoice, verified_by_user_id: str) -> None:
    invoice.status = "verified"
    invoice.verified_at = datetime.utcnow()
    invoice.verified_by = verified_by_user_id

    user = invoice.user
    user.trial_ends_at = datetime.utcnow() + timedelta(days=invoice.duration_days)

    db.commit()
