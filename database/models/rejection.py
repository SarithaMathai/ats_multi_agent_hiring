import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDMixin


class Rejection(UUIDMixin, Base):
    __tablename__ = "rejections"
    __table_args__ = {"schema": "ats"}

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ats.candidates.id", ondelete="CASCADE")
    )
    stage_name: Mapped[str] = mapped_column()
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason_category: Mapped[str] = mapped_column()
    reason_detail: Mapped[str | None] = mapped_column(nullable=True)
    rejected_by_interviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ats.interviewers.id", ondelete="SET NULL"), nullable=True
    )
