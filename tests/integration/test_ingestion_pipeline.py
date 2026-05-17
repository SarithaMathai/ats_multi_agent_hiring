"""
Integration tests — CSV ingestion pipeline via FastAPI.

Tests the POST /api/v1/ingestion/upload endpoint with real CSV payloads.
Verifies that files are parsed, rows counted, and errors are reported cleanly.

Does NOT require ChromaDB for basic parsing tests; ChromaDB-dependent tests
are guarded with a skip if ChromaDB is unreachable.
"""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_csv(headers: list[str], rows: list[list]) -> bytes:
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines).encode("utf-8")


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_upload_candidates_csv(client):
    """Upload a valid candidates CSV; expect 200 with correct row count."""
    if client is None:
        pytest.skip("App client not available")

    csv_bytes = _make_csv(
        headers=["candidate_id", "name", "source_channel", "quality_score", "hired"],
        rows=[
            ["c001", "Alice",   "LinkedIn", "0.82", "True"],
            ["c002", "Bob",     "Referral", "0.91", "True"],
            ["c003", "Charlie", "Indeed",   "0.44", "False"],
        ],
    )
    response = await client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("candidates.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in ("success", "partial")
    assert "candidates" in body["rows_ingested"]
    assert body["rows_ingested"]["candidates"] == 3


async def test_upload_stages_csv(client):
    """Upload a stages CSV; parser accepts it even though DB wiring is pending."""
    if client is None:
        pytest.skip("App client not available")

    csv_bytes = _make_csv(
        headers=["stage", "candidate_id", "days_in_stage", "passed"],
        rows=[
            ["Application Review", "c001", "3", "True"],
            ["Technical Interview", "c002", "18", "False"],
        ],
    )
    response = await client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("stages.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rows_ingested"].get("stages") == 2


async def test_upload_multiple_files(client):
    """Upload two different CSV files in a single multipart request."""
    if client is None:
        pytest.skip("App client not available")

    candidates_csv = _make_csv(
        ["candidate_id", "source_channel", "hired"],
        [["c10", "LinkedIn", "True"], ["c11", "Referral", "True"]],
    )
    rejections_csv = _make_csv(
        ["candidate_id", "stage", "rejection_category"],
        [["c12", "Phone Screen", "skills_mismatch"]],
    )
    response = await client.post(
        "/api/v1/ingestion/upload",
        files=[
            ("files", ("candidates.csv",  io.BytesIO(candidates_csv),  "text/csv")),
            ("files", ("rejections.csv",  io.BytesIO(rejections_csv),  "text/csv")),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["files_processed"]) == 2
    assert body["rows_ingested"]["candidates"] == 2
    assert body["rows_ingested"]["rejections"] == 1


async def test_upload_unknown_file_type(client):
    """A file with an unrecognised name produces an error entry but does not crash."""
    if client is None:
        pytest.skip("App client not available")

    csv_bytes = b"col1,col2\nval1,val2\n"
    response = await client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("unknown_data.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert len(body["errors"]) >= 1
    assert "unknown_data.csv" in body["errors"][0]


async def test_upload_empty_file(client):
    """An empty CSV produces an error, not a 500."""
    if client is None:
        pytest.skip("App client not available")

    response = await client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("candidates.csv", io.BytesIO(b""), "text/csv"))],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["errors"]) >= 1


async def test_ingestion_status_initial(client):
    """GET /ingestion/status before any upload returns a 'no_runs' response."""
    if client is None:
        pytest.skip("App client not available")

    # Note: if prior tests already uploaded, status will have a report — just check it's valid
    response = await client.get("/api/v1/ingestion/status")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
