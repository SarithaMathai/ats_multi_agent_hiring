"""
Maps CSV column names to SQLAlchemy model attribute names where they differ.
Columns listed in CHROMA_ONLY are not stored in Postgres — only embedded into ChromaDB.
"""

# Columns in candidates.csv that go to ChromaDB, not the Postgres table
CANDIDATE_CHROMA_ONLY = {"skills", "background"}

# Columns in stages.csv that go to ChromaDB, not the Postgres table
STAGE_CHROMA_ONLY = {"feedback"}

# Nullable FK columns — empty string should become None
NULLABLE_FK_COLUMNS = {
    "interviewer_id",
    "rejected_by_interviewer_id",
    "responded_at",
    "exited_at",
    "rejection_reason",
}

# Date columns that need parsing
DATETIME_COLUMNS = {
    "created_at", "updated_at", "offered_at",
    "responded_at", "entered_at", "exited_at", "rejected_at",
}
