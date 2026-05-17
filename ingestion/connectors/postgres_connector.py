"""
Upsert validated rows into PostgreSQL using SQLAlchemy async session.
Each function handles one entity type and is idempotent — safe to re-run.
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.candidate import Candidate
from database.models.interview_stage import InterviewStage
from database.models.interviewer import Interviewer
from database.models.offer import Offer
from database.models.rejection import Rejection
from ingestion.pipeline.field_mappings import NULLABLE_FK_COLUMNS


# ── Type helpers ───────────────────────────────────────────────────────────────

def _uuid(val: str | None) -> uuid.UUID | None:
    if not val or str(val).strip() == "":
        return None
    return uuid.UUID(str(val).strip())


def _req_uuid(val: str) -> uuid.UUID:
    return uuid.UUID(str(val).strip())


def _dt(val: str | None) -> datetime | None:
    if not val or str(val).strip() == "":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised datetime format: {val!r}")


def _req_dt(val: str) -> datetime:
    result = _dt(val)
    if result is None:
        raise ValueError(f"Required datetime is empty: {val!r}")
    return result


def _float(val: str | None) -> float | None:
    if not val or str(val).strip() == "":
        return None
    return float(str(val).strip())


def _bool(val: str | None) -> bool:
    if val is None:
        return True
    return str(val).strip().lower() in ("true", "1", "yes")


# ── Upsert functions ───────────────────────────────────────────────────────────

async def upsert_interviewers(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        pk = _req_uuid(row["id"])
        obj = await session.get(Interviewer, pk)
        if obj is None:
            obj = Interviewer()
        obj.id         = pk
        obj.name       = row["name"]
        obj.email      = row["email"]
        obj.department = row["department"]
        obj.role       = row["role"]
        obj.is_active  = _bool(row.get("is_active"))
        session.add(obj)
        count += 1
    await session.commit()
    return count


async def upsert_candidates(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        pk = _req_uuid(row["id"])
        obj = await session.get(Candidate, pk)
        if obj is None:
            obj = Candidate()
        obj.id               = pk
        obj.name             = row["name"]
        obj.source_channel   = row["source_channel"]
        obj.position         = row["position"]
        obj.experience_years = float(row["experience_years"])
        obj.current_stage    = row["current_stage"]
        obj.overall_status   = row["overall_status"]
        # created_at preserved from CSV; updated_at refreshed
        if row.get("created_at"):
            obj.created_at = _req_dt(row["created_at"])
        session.add(obj)
        count += 1
    await session.commit()
    return count


async def upsert_stages(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        pk = _req_uuid(row["id"])
        obj = await session.get(InterviewStage, pk)
        if obj is None:
            obj = InterviewStage()
        obj.id             = pk
        obj.candidate_id   = _req_uuid(row["candidate_id"])
        obj.stage_name     = row["stage_name"]
        obj.entered_at     = _req_dt(row["entered_at"])
        obj.exited_at      = _dt(row.get("exited_at"))
        obj.outcome        = row.get("outcome") or None
        obj.interviewer_id = _uuid(row.get("interviewer_id"))
        obj.duration_hours = _float(row.get("duration_hours"))
        session.add(obj)
        count += 1
    await session.commit()
    return count


async def upsert_offers(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        pk = _req_uuid(row["id"])
        obj = await session.get(Offer, pk)
        if obj is None:
            obj = Offer()
        obj.id               = pk
        obj.candidate_id     = _req_uuid(row["candidate_id"])
        obj.position         = row["position"]
        obj.salary_offered   = float(row["salary_offered"])
        obj.currency         = row.get("currency") or "USD"
        obj.offered_at       = _req_dt(row["offered_at"])
        obj.responded_at     = _dt(row.get("responded_at"))
        obj.status           = row["status"]
        obj.rejection_reason = row.get("rejection_reason") or None
        session.add(obj)
        count += 1
    await session.commit()
    return count


async def upsert_rejections(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        pk = _req_uuid(row["id"])
        obj = await session.get(Rejection, pk)
        if obj is None:
            obj = Rejection()
        obj.id                          = pk
        obj.candidate_id                = _req_uuid(row["candidate_id"])
        obj.stage_name                  = row["stage_name"]
        obj.rejected_at                 = _req_dt(row["rejected_at"])
        obj.reason_category             = row["reason_category"]
        obj.reason_detail               = row.get("reason_detail") or None
        obj.rejected_by_interviewer_id  = _uuid(row.get("rejected_by_interviewer_id"))
        session.add(obj)
        count += 1
    await session.commit()
    return count
