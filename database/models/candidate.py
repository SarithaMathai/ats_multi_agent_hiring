from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, TimestampMixin, UUIDMixin


class Candidate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = {"schema": "ats"}

    name: Mapped[str] = mapped_column()
    source_channel: Mapped[str] = mapped_column()
    position: Mapped[str] = mapped_column()
    experience_years: Mapped[float] = mapped_column()
    current_stage: Mapped[str] = mapped_column()
    overall_status: Mapped[str] = mapped_column()
