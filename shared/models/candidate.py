import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    source_channel: str
    position: str
    experience_years: float
    current_stage: str
    overall_status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
