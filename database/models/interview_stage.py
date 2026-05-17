import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, UUIDMixin


class InterviewStage(UUIDMixin, Base):
    __tablename__ = "interview_stages"
    __table_args__ = {"schema": "ats"}

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ats.candidates.id", ondelete="CASCADE")
    )
    stage_name: Mapped[str] = mapped_column()
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(nullable=True)
    interviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ats.interviewers.id", ondelete="SET NULL"), nullable=True
    )
    duration_hours: Mapped[float | None] = mapped_column(nullable=True)
