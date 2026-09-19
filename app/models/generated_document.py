import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=True, index=True)
    doc_id: Mapped[str] = mapped_column(String(255), nullable=False)  # the generated file's stem, used to download it
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    jv_name: Mapped[str] = mapped_column(String(255), default="")
    partner_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
