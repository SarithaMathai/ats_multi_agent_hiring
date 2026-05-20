from sqlalchemy.orm import Mapped, mapped_column

from database.models.base import Base, TimestampMixin, UUIDMixin


class Interviewer(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "interviewers"
    __table_args__ = {"schema": "ats"}

    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column(unique=True)
    department: Mapped[str] = mapped_column()
    role: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
