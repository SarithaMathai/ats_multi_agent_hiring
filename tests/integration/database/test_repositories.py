"""
Integration tests — PostgreSQL database layer.

Tests insert, query, and rollback against the real database.
Each test runs inside a transaction that is rolled back at the end,
so the database is left clean after the suite.

Requires: PostgreSQL running and DATABASE_URL set in .env
Skip automatically if the database is unreachable.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from configs.settings import settings

pytestmark = pytest.mark.integration


# ── DB availability guard ─────────────────────────────────────────────────────

def _db_available() -> bool:
    try:
        import asyncpg, asyncio
        async def _ping():
            conn = await asyncpg.connect(
                settings.database.url.replace("+asyncpg", ""), timeout=3
            )
            await conn.close()
        asyncio.get_event_loop().run_until_complete(_ping())
        return True
    except Exception:
        return False


skip_if_no_db = pytest.mark.skipif(
    not _db_available(),
    reason="PostgreSQL not reachable — skipping DB integration tests",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_session():
    """Yield a real AsyncSession wrapped in a rolled-back transaction."""
    engine = create_async_engine(settings.database.url, echo=False)
    async with engine.begin() as conn:
        # Nest a savepoint so we can roll back after each test
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            yield session
            await session.rollback()
    await engine.dispose()


# ── Tests ─────────────────────────────────────────────────────────────────────

@skip_if_no_db
async def test_db_connection(db_session: AsyncSession):
    """Database is reachable and returns a row from a trivial query."""
    result = await db_session.execute(text("SELECT 1 AS val"))
    row = result.fetchone()
    assert row is not None
    assert row.val == 1


@skip_if_no_db
async def test_candidate_insert_and_query(db_session: AsyncSession):
    """Insert a Candidate row and read it back within the same transaction."""
    from database.models.candidate import Candidate

    candidate_id = uuid.uuid4()
    candidate = Candidate(
        id=candidate_id,
        name="Test Candidate",
        source_channel="LinkedIn",
        position="SWE",
        experience_years=5.0,
        current_stage="Technical Interview",
        overall_status="active",
    )
    db_session.add(candidate)
    await db_session.flush()  # write to DB without committing

    result = await db_session.get(Candidate, candidate_id)
    assert result is not None
    assert result.name == "Test Candidate"
    assert result.source_channel == "LinkedIn"
    assert result.position == "SWE"


@skip_if_no_db
async def test_multiple_candidates_bulk_insert(db_session: AsyncSession):
    """Insert 5 candidates and verify count increases within the transaction."""
    from database.models.candidate import Candidate

    ids = [uuid.uuid4() for _ in range(5)]
    candidates = [
        Candidate(
            id=cid,
            name=f"Candidate {i}",
            source_channel=["LinkedIn", "Referral", "Indeed"][i % 3],
            position="SWE",
            experience_years=float(i + 1),
            current_stage="Application Review",
            overall_status="active",
        )
        for i, cid in enumerate(ids)
    ]
    db_session.add_all(candidates)
    await db_session.flush()

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM ats.candidates WHERE name LIKE 'Candidate %'")
    )
    count = result.scalar()
    assert count >= 5


@skip_if_no_db
async def test_interviewer_insert(db_session: AsyncSession):
    """Insert an Interviewer row and verify fields."""
    from database.models.interviewer import Interviewer

    iid = uuid.uuid4()
    interviewer = Interviewer(
        id=iid,
        name="Alice Smith",
        email=f"alice-{iid}@company.com",   # unique per run
        department="Engineering",
        role="Senior Engineer",
        is_active=True,
    )
    db_session.add(interviewer)
    await db_session.flush()

    result = await db_session.get(Interviewer, iid)
    assert result is not None
    assert result.name == "Alice Smith"
    assert result.department == "Engineering"
    assert result.role == "Senior Engineer"
