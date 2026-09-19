import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PartnerProfile(Base):
    __tablename__ = "partner_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # lead | first | second (origin role)
    partner_name: Mapped[str] = mapped_column(String(255), default="")
    partner_short: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    partner_ceo: Mapped[str] = mapped_column(String(255), default="")
    partner_md1: Mapped[str] = mapped_column(String(255), default="")
    partner_md2: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="profiles")
    images: Mapped[list["ProfileImage"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    attachments: Mapped[list["ProfileAttachment"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class ProfileImage(Base):
    __tablename__ = "profile_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("partner_profiles.id"), nullable=False, index=True)
    img_key: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. LEAD_CEO_SIG
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    profile: Mapped["PartnerProfile"] = relationship(back_populates="images")


class ProfileAttachment(Base):
    __tablename__ = "profile_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("partner_profiles.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(500), default="")

    profile: Mapped["PartnerProfile"] = relationship(back_populates="attachments")
