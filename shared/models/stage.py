import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StageRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    candidate_id: uuid.UUID
    stage_name: str
    entered_at: datetime
    exited_at: datetime | None = None
    outcome: str | None = None
    interviewer_id: uuid.UUID | None = None
    duration_hours: float | None = None
