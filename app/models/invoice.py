import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

# pending    -> created, awaiting the user to pay & submit proof
# submitted  -> user submitted proof, awaiting admin verification
# verified   -> admin confirmed payment; user's access was extended
# rejected   -> admin rejected the submitted proof; user must resubmit
INVOICE_STATUSES = ("pending", "submitted", "verified", "rejected")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)

    proof_image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    proof_reference: Mapped[str] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), default="")

    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="invoices", foreign_keys=[user_id])
