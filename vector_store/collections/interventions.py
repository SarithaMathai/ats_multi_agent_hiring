from pydantic import BaseModel

from configs.settings import settings
from vector_store.chroma.collection_manager import get_or_create_collection


class CaseStudy(BaseModel):
    case_study_id: str
    title: str
    issue_type: str
    observed_impact_pct: float
    implementation_weeks: int
    excerpt: str


class BestPractice(BaseModel):
    practice_id: str
    title: str
    steps: list[str]
    typical_timeline_weeks: int
    applicable_roles: list[str]


class InterventionsCollection:
    """Backs MCP tool 1 (search_similar_interventions) and tool 2 (fetch_best_practices_by_issue)."""

    def __init__(self) -> None:
        self._col = get_or_create_collection(settings.chroma.collection_interventions)

    # ── Write ──────────────────────────────────────────────────────────────────

    def add_intervention(
        self,
        case_study_id: str,
        issue_text: str,
        embedding: list[float],
        role: str,
        outcome_text: str,
        issue_type: str,
        observed_impact_pct: float = 0.0,
        implementation_weeks: int = 4,
    ) -> None:
        self._col.add(
            ids=[case_study_id],
            documents=[issue_text],
            embeddings=[embedding],
            metadatas=[
                {
                    "role": role,
                    "outcome": outcome_text,
                    "issue_type": issue_type,
                    "observed_impact_pct": observed_impact_pct,
                    "implementation_weeks": implementation_weeks,
                }
            ],
        )

    # ── MCP Tool 1 — search_similar_interventions ──────────────────────────────

    def search_by_issue(
        self,
        query_embedding: list[float],
        role: str | None = None,
        n_results: int = 3,
    ) -> list[CaseStudy]:
        filters = {"role": role} if role else None
        results = self._col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )
        case_studies = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        for id_, doc, meta in zip(ids, docs, metas):
            case_studies.append(
                CaseStudy(
                    case_study_id=id_,
                    title=meta.get("outcome", "")[:80],
                    issue_type=meta.get("issue_type", ""),
                    observed_impact_pct=float(meta.get("observed_impact_pct", 0)),
                    implementation_weeks=int(meta.get("implementation_weeks", 4)),
                    excerpt=doc[:300],
                )
            )
        return case_studies

    # ── MCP Tool 2 — fetch_best_practices_by_issue ─────────────────────────────

    def get_by_issue_type(self, issue_type: str) -> list[BestPractice]:
        results = self._col.get(
            where={"issue_type": issue_type},
            include=["documents", "metadatas"],
        )
        practices = []
        ids = results.get("ids", [])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        for id_, doc, meta in zip(ids, docs, metas):
            practices.append(
                BestPractice(
                    practice_id=id_,
                    title=meta.get("outcome", "")[:80],
                    steps=_parse_steps(doc),
                    typical_timeline_weeks=int(meta.get("implementation_weeks", 4)),
                    applicable_roles=[meta.get("role", "all")],
                )
            )
        return practices


def _parse_steps(text: str) -> list[str]:
    """Split stored document text into actionable steps on newlines or sentences."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines if lines else [text[:200]]
