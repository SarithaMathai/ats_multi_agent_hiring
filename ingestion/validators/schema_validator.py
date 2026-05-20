"""
Validate required fields before DB insertion.
Returns (valid_rows, skipped_count) so the pipeline can report bad records
without stopping the whole run.
"""

from dataclasses import dataclass

REQUIRED: dict[str, list[str]] = {
    "interviewers": ["id", "name", "email", "department", "role"],
    "candidates":   ["id", "name", "source_channel", "position", "experience_years", "overall_status"],
    "stages":       ["id", "candidate_id", "stage_name", "entered_at", "outcome"],
    "offers":       ["id", "candidate_id", "position", "salary_offered", "status"],
    "rejections":   ["id", "candidate_id", "stage_name", "rejected_at", "reason_category"],
}


@dataclass
class ValidationResult:
    entity: str
    valid: list[dict]
    skipped: int
    errors: list[str]


def validate(entity: str, rows: list[dict]) -> ValidationResult:
    required_cols = REQUIRED.get(entity, [])
    valid, errors = [], []

    for i, row in enumerate(rows):
        missing = [c for c in required_cols if not row.get(c)]
        if missing:
            errors.append(f"Row {i} missing: {missing}  id={row.get('id', '?')}")
        else:
            valid.append(row)

    return ValidationResult(
        entity=entity,
        valid=valid,
        skipped=len(rows) - len(valid),
        errors=errors,
    )
