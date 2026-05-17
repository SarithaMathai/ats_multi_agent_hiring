"""
Orchestrates the full ETL run in two phases:
  Phase 1 — PostgreSQL: parse CSV → validate → upsert (FK order)
  Phase 2 — ChromaDB:   embed text fields → upsert into collections
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from database.sessions.async_session import AsyncSessionLocal
from ingestion.connectors import chroma_connector as chroma
from ingestion.connectors import postgres_connector as pg
from ingestion.parsers.csv_parser import (
    parse_candidates,
    parse_interviewers,
    parse_offers,
    parse_rejections,
    parse_stages,
)
from ingestion.validators.schema_validator import validate
from vector_store.chroma.collection_manager import initialise_all_collections


@dataclass
class IngestionReport:
    postgres: dict[str, int] = field(default_factory=dict)
    chroma:   dict[str, int] = field(default_factory=dict)
    skipped:  dict[str, int] = field(default_factory=dict)
    errors:   list[str]      = field(default_factory=list)

    def print(self) -> None:
        print("\n=== Ingestion Report ===")
        print("  PostgreSQL rows upserted:")
        for entity, count in self.postgres.items():
            print(f"    {entity:<20} {count}")
        print("  ChromaDB documents upserted:")
        for col, count in self.chroma.items():
            print(f"    {col:<20} {count}")
        if self.skipped:
            print("  Skipped (validation failures):")
            for entity, count in self.skipped.items():
                print(f"    {entity:<20} {count}")
        if self.errors:
            print("  Errors:")
            for e in self.errors[:10]:
                print(f"    {e}")


class IngestionPipeline:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.report = IngestionReport()

    async def run(self) -> IngestionReport:
        await self._phase1_postgres()
        await self._phase2_chroma()
        return self.report

    # ── Phase 1 — PostgreSQL ────────────────────────────────────────────────────

    async def _phase1_postgres(self) -> None:
        print("\n[Phase 1] Loading PostgreSQL...")

        # Parse all files up front
        interviewers = parse_interviewers(self.data_dir / "interviewers.csv")
        candidates   = parse_candidates(self.data_dir / "candidates.csv")
        stages       = parse_stages(self.data_dir / "stages.csv")
        offers       = parse_offers(self.data_dir / "offers.csv")
        rejections   = parse_rejections(self.data_dir / "rejections.csv")

        # Validate
        def _validate(entity: str, rows: list[dict]) -> list[dict]:
            result = validate(entity, rows)
            self.report.skipped[entity] = result.skipped
            self.report.errors.extend(result.errors)
            return result.valid

        valid_interviewers = _validate("interviewers", interviewers)
        valid_candidates   = _validate("candidates",   candidates)
        valid_stages       = _validate("stages",       stages)
        valid_offers       = _validate("offers",       offers)
        valid_rejections   = _validate("rejections",   rejections)

        # Upsert in FK order
        async with AsyncSessionLocal() as session:
            n = await pg.upsert_interviewers(session, valid_interviewers)
            print(f"  interviewers      {n}")
            self.report.postgres["interviewers"] = n

            n = await pg.upsert_candidates(session, valid_candidates)
            print(f"  candidates        {n}")
            self.report.postgres["candidates"] = n

            n = await pg.upsert_stages(session, valid_stages)
            print(f"  interview_stages  {n}")
            self.report.postgres["interview_stages"] = n

            n = await pg.upsert_offers(session, valid_offers)
            print(f"  offers            {n}")
            self.report.postgres["offers"] = n

            n = await pg.upsert_rejections(session, valid_rejections)
            print(f"  rejections        {n}")
            self.report.postgres["rejections"] = n

        # Store parsed rows for Phase 2
        self._candidates = candidates
        self._stages     = stages

    # ── Phase 2 — ChromaDB ──────────────────────────────────────────────────────

    async def _phase2_chroma(self) -> None:
        print("\n[Phase 2] Loading ChromaDB...")
        initialise_all_collections()

        n = chroma.embed_candidates(self._candidates)
        print(f"  ats_candidates    {n} docs")
        self.report.chroma["ats_candidates"] = n

        n = chroma.embed_resumes(self._candidates)
        print(f"  ats_resumes       {n} docs")
        self.report.chroma["ats_resumes"] = n

        n = chroma.embed_feedback(self._stages)
        print(f"  ats_feedback      {n} docs")
        self.report.chroma["ats_feedback"] = n

        interventions_path = self.data_dir / "interventions.json"
        interventions = json.loads(interventions_path.read_text(encoding="utf-8"))
        n = chroma.embed_interventions(interventions)
        print(f"  ats_interventions {n} docs")
        self.report.chroma["ats_interventions"] = n
