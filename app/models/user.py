import uuid
from datetime import datetime, timedelta

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

TRIAL_DAYS = 30


def _default_trial_end() -> datetime:
    return datetime.utcnow() + timedelta(days=TRIAL_DAYS)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    preferred_locale: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[str] = mapped_column(String(64), nullable=True)
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime, default=_default_trial_end, nullable=False)

    password_reset_token: Mapped[str] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    pending_email: Mapped[str] = mapped_column(String(255), nullable=True)
    pending_email_token: Mapped[str] = mapped_column(String(64), nullable=True)

    # Lead Partner is always available. These gate First/Second Partner
    # tabs and signature/stamp uploads — off by default for new accounts,
    # an admin grants them per client.
    can_use_first_partner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_use_second_partner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_upload_signature_stamp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Per-user subscription pricing, set by an admin. An invoice is only
    # auto-generated once both are set — until then a user past trial just
    # sees a generic "contact support" lock, not a $0 invoice.
    subscription_amount: Mapped[float] = mapped_column(Float, nullable=True)
    subscription_duration_days: Mapped[int] = mapped_column(Integer, nullable=True)

    profiles: Mapped[list["PartnerProfile"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="Invoice.user_id")

    @property
    def trial_expired(self) -> bool:
        return datetime.utcnow() > self.trial_ends_at
