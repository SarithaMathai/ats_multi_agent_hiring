"""
Run the full ATS data ingestion pipeline.

Prerequisites:
  1. docker compose up -d postgres chromadb
  2. poetry run alembic upgrade head
  3. poetry run python scripts/generate_seed_data.py

Usage:
  poetry run python scripts/seed_data.py
"""

import asyncio
from pathlib import Path

from ingestion.pipeline.ingestion_pipeline import IngestionPipeline

DATA_DIR = Path("data")


async def main() -> None:
    if not DATA_DIR.exists():
        print("ERROR: data/ directory not found.")
        print("Run:  poetry run python scripts/generate_seed_data.py")
        return

    missing = [
        f for f in [
            "interviewers.csv", "candidates.csv", "stages.csv",
            "offers.csv", "rejections.csv", "interventions.json",
        ]
        if not (DATA_DIR / f).exists()
    ]
    if missing:
        print(f"ERROR: Missing data files: {missing}")
        return

    print("Starting ATS ingestion pipeline...")
    pipeline = IngestionPipeline(data_dir=DATA_DIR)
    report = await pipeline.run()
    report.print()
    print("\nIngestion complete.")


if __name__ == "__main__":
    asyncio.run(main())
