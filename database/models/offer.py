import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, TimestampMixin, UUIDMixin


class Offer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "offers"
    __table_args__ = {"schema": "ats"}

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ats.candidates.id", ondelete="CASCADE")
    )
    position: Mapped[str] = mapped_column()
    salary_offered: Mapped[float] = mapped_column()
    currency: Mapped[str] = mapped_column(default="USD")
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column()
    rejection_reason: Mapped[str | None] = mapped_column(nullable=True)
