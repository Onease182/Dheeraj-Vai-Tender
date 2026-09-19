import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    linked_profiles: Mapped[dict] = mapped_column(JSONB, default=dict)  # {role: profile_id}
    employer_pdf_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="drafts")
    images: Mapped[list["DraftImage"]] = relationship(back_populates="draft", cascade="all, delete-orphan")
    session_docs: Mapped[list["DraftSessionDoc"]] = relationship(back_populates="draft", cascade="all, delete-orphan")


class DraftImage(Base):
    __tablename__ = "draft_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=False, index=True)
    img_key: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    draft: Mapped["Draft"] = relationship(back_populates="images")


class DraftSessionDoc(Base):
    __tablename__ = "draft_session_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    draft: Mapped["Draft"] = relationship(back_populates="session_docs")
