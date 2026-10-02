import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    organization: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(100), nullable=True)   # Civil, Goods, Consultancy …
    district: Mapped[str] = mapped_column(String(100), nullable=True)
    budget: Mapped[str] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # source: "ppmo" | "newspaper"
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ppmo")
    source_url: Mapped[str] = mapped_column(Text, nullable=True)        # direct link to notice
    newspaper_name: Mapped[str] = mapped_column(String(200), nullable=True)

    publication_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
