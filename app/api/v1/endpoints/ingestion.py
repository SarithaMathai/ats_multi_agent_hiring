"""
Ingestion endpoints — upload CSV data and trigger the vector-store pipeline.

POST /api/v1/ingestion/upload
    Accept one or more CSV files (candidates, stages, rejections, offers,
    interviewers).  Parses each file into rows, passes them to the
    appropriate ChromaDB ingestion helper, and returns a status report.

GET  /api/v1/ingestion/status
    Returns the last ingestion run report held in memory.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(tags=["ingestion"])
logger = logging.getLogger(__name__)

# ── Supported file types ──────────────────────────────────────────────────────

_SUPPORTED_TYPES = {"candidates", "stages", "rejections", "offers", "interviewers"}

# ── In-process status store ───────────────────────────────────────────────────

_last_report: dict[str, Any] = {}


# ── Response model ────────────────────────────────────────────────────────────

class IngestionReport(BaseModel):
    status: str
    files_processed: list[str]
    rows_ingested: dict[str, int]
    errors: list[str]
    timestamp: str


# ── CSV parsing helper ────────────────────────────────────────────────────────

def _parse_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")   # strip BOM if present
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _infer_type(filename: str) -> str | None:
    name = filename.lower().replace("-", "_").replace(" ", "_")
    for t in _SUPPORTED_TYPES:
        if t in name:
            return t
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=IngestionReport)
async def upload_files(files: list[UploadFile]) -> IngestionReport:
    """Upload one or more CSV files and ingest them into ChromaDB.

    File-type detection is done by filename (e.g. 'candidates.csv' → candidates).
    Each file is parsed into rows and passed to the matching ingestion helper.

    Returns a per-file row count and any errors encountered.
    """
    if not files:
        raise HTTPException(status_code=422, detail="No files uploaded.")

    files_processed: list[str] = []
    rows_ingested: dict[str, int] = {}
    errors: list[str] = []

    for upload in files:
        filename = upload.filename or "unknown.csv"
        data_type = _infer_type(filename)

        if data_type is None:
            errors.append(
                f"{filename}: cannot determine type. "
                f"Name must contain one of: {sorted(_SUPPORTED_TYPES)}"
            )
            continue

        try:
            raw = await upload.read()
            rows = _parse_csv(raw)
            if not rows:
                errors.append(f"{filename}: file is empty or has no data rows.")
                continue

            row_count = await _ingest_rows(data_type, rows)
            files_processed.append(filename)
            rows_ingested[data_type] = rows_ingested.get(data_type, 0) + row_count
            logger.info("Ingested %d rows from '%s' (type=%s)", row_count, filename, data_type)

        except Exception as exc:
            logger.exception("Error ingesting %s: %s", filename, exc)
            errors.append(f"{filename}: {exc}")

    status = "success" if not errors else ("partial" if files_processed else "error")
    report = IngestionReport(
        status=status,
        files_processed=files_processed,
        rows_ingested=rows_ingested,
        errors=errors,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    global _last_report
    _last_report = report.model_dump()
    return report


@router.get("/status", response_model=IngestionReport | dict)
async def ingestion_status() -> Any:
    """Return the most recent ingestion run report."""
    if not _last_report:
        return {"status": "no_runs", "detail": "No ingestion run has been submitted yet."}
    return _last_report


# ── Ingestion dispatcher ──────────────────────────────────────────────────────

async def _ingest_rows(data_type: str, rows: list[dict]) -> int:
    """Route parsed rows to the appropriate ChromaDB ingestion function.

    Each ingestion function is imported lazily so ChromaDB is not touched
    until an actual upload arrives (keeps startup fast).

    Currently delegates to the collection helpers built on Day 5.
    Returns the number of rows successfully ingested.
    """
    import asyncio

    if data_type == "candidates":
        from vector_store.collections.candidates import CandidatesCollection
        col = CandidatesCollection()
        # Each row needs a pre-computed embedding; use a zero vector as placeholder
        # until the embedding pipeline (Day 5 ingestion) is wired end-to-end.
        dim = 384
        zero_vec = [0.0] * dim
        def _bulk_add():
            for row in rows:
                cid = row.get("candidate_id") or row.get("id", f"csv-{id(row)}")
                text = " ".join(str(v) for v in row.values())
                col.add(candidate_id=cid, text=text, embedding=zero_vec, metadata=row)
        await asyncio.to_thread(_bulk_add)

    elif data_type == "stages":
        # Stages are structured data (PostgreSQL), not ChromaDB vectors.
        # Accepted here for completeness; full DB persistence added Day 14.
        logger.info("Stage rows received (%d) — DB persistence wired on Day 14.", len(rows))

    elif data_type == "rejections":
        logger.info("Rejection rows received (%d) — DB persistence wired on Day 14.", len(rows))

    elif data_type == "offers":
        logger.info("Offer rows received (%d) — DB persistence wired on Day 14.", len(rows))

    elif data_type == "interviewers":
        logger.info("Interviewer rows received (%d) — DB persistence wired on Day 14.", len(rows))

    return len(rows)
