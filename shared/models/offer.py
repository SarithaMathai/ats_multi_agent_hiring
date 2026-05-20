import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OfferRecord(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    candidate_id: uuid.UUID
    position: str
    salary_offered: float
    currency: str = "USD"
    offered_at: datetime
    responded_at: datetime | None = None
    status: str
    rejection_reason: str | None = None
