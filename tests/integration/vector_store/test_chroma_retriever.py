"""
Integration tests — ChromaDB vector store.

Tests add, search, and delete against the real ChromaDB instance.
Each test uses a unique ID prefix and cleans up after itself so the
collection is not polluted between runs.

Requires: ChromaDB running at CHROMA_HOST:CHROMA_PORT
Skip automatically if ChromaDB is unreachable.
"""
from __future__ import annotations

import pytest

from configs.settings import settings

pytestmark = pytest.mark.integration

# ── ChromaDB availability guard ───────────────────────────────────────────────

def _chroma_available() -> bool:
    try:
        from vector_store.chroma.client import get_chroma_client
        client = get_chroma_client()
        client.heartbeat()
        return True
    except Exception:
        return False


skip_if_no_chroma = pytest.mark.skipif(
    not _chroma_available(),
    reason="ChromaDB not reachable — skipping vector store integration tests",
)

# Fixed-dimension zero-vector (all-MiniLM-L6-v2 produces 384-dim vectors)
_DIM = 384
_ZERO_VEC = [0.0] * _DIM
_TEST_VEC  = [0.1] * _DIM   # non-zero so distance calculation works


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def candidates_col():
    """Return the CandidatesCollection and clean up test docs after the test."""
    from vector_store.collections.candidates import CandidatesCollection
    col = CandidatesCollection()
    test_ids: list[str] = []
    yield col, test_ids
    # Cleanup — delete every doc we inserted
    for doc_id in test_ids:
        try:
            col.delete(doc_id)
        except Exception:
            pass


@pytest.fixture
def interventions_col():
    """Return the InterventionsCollection and clean up test docs after the test."""
    from vector_store.collections.interventions import InterventionsCollection
    col = InterventionsCollection()
    test_ids: list[str] = []
    yield col, test_ids
    for doc_id in test_ids:
        try:
            col._col.delete(ids=[doc_id])
        except Exception:
            pass


# ── Tests ─────────────────────────────────────────────────────────────────────

@skip_if_no_chroma
def test_chroma_heartbeat():
    """ChromaDB server responds to heartbeat."""
    from vector_store.chroma.client import get_chroma_client
    client = get_chroma_client()
    result = client.heartbeat()
    assert result is not None


@skip_if_no_chroma
def test_candidates_add_and_search(candidates_col):
    """Add a candidate document and retrieve it via semantic search."""
    col, test_ids = candidates_col
    doc_id = "test-cand-001"
    test_ids.append(doc_id)

    col.add(
        candidate_id=doc_id,
        text="Senior software engineer with 8 years experience in Python and distributed systems",
        embedding=_TEST_VEC,
        metadata={"source_channel": "LinkedIn", "position": "SWE"},
    )

    results = col.search(query_embedding=_TEST_VEC, n_results=5)
    found = [r for r in results if r["id"] == doc_id]
    assert len(found) == 1, f"Inserted doc not found in search results: {results}"
    assert found[0]["metadata"]["source_channel"] == "LinkedIn"


@skip_if_no_chroma
def test_candidates_delete(candidates_col):
    """Add then delete a candidate; subsequent search should not return it."""
    col, test_ids = candidates_col
    doc_id = "test-cand-del-001"

    col.add(
        candidate_id=doc_id,
        text="Mid-level product manager with 4 years experience",
        embedding=_TEST_VEC,
        metadata={"source_channel": "Referral"},
    )

    col.delete(doc_id)
    # Do NOT add to test_ids — already deleted

    results = col.search(query_embedding=_TEST_VEC, n_results=10)
    ids = [r["id"] for r in results]
    assert doc_id not in ids, "Deleted document should not appear in search results"


@skip_if_no_chroma
def test_interventions_add_and_search(interventions_col):
    """Add an intervention case study and retrieve it via semantic search."""
    col, test_ids = interventions_col
    case_id = "test-intervention-001"
    test_ids.append(case_id)

    col.add_intervention(
        case_study_id=case_id,
        issue_text="Technical interview stage taking 3 weeks causing candidate dropout",
        embedding=_TEST_VEC,
        role="Software Engineer",
        outcome_text="Reduced tech interview cycle by 40% using async video screening",
        issue_type="slow_assessment",
        observed_impact_pct=40.0,
        implementation_weeks=6,
    )

    results = col.search_by_issue(query_embedding=_TEST_VEC, n_results=5)
    found = [r for r in results if r.case_study_id == case_id]
    assert len(found) == 1, f"Inserted case study not found: {[r.case_study_id for r in results]}"
    assert found[0].issue_type == "slow_assessment"
    assert found[0].observed_impact_pct == 40.0


@skip_if_no_chroma
def test_interventions_filter_by_role(interventions_col):
    """Role filter returns only matching entries."""
    col, test_ids = interventions_col
    swe_id = "test-intervention-swe-001"
    pm_id  = "test-intervention-pm-001"
    test_ids.extend([swe_id, pm_id])

    col.add_intervention(
        case_study_id=swe_id,
        issue_text="Slow technical assessment for engineers",
        embedding=_TEST_VEC,
        role="Software Engineer",
        outcome_text="Automated coding challenge reduced cycle 30%",
        issue_type="slow_assessment",
    )
    col.add_intervention(
        case_study_id=pm_id,
        issue_text="Slow case study review for PMs",
        embedding=_TEST_VEC,
        role="Product Manager",
        outcome_text="Live case study replaced written exercise",
        issue_type="slow_assessment",
    )

    swe_results = col.search_by_issue(
        query_embedding=_TEST_VEC, role="Software Engineer", n_results=5
    )
    pm_ids = [r.case_study_id for r in swe_results]
    assert pm_id not in pm_ids, "PM case study leaked into SWE-filtered results"


@skip_if_no_chroma
def test_collection_initialise_all():
    """initialise_all_collections creates all 4 named collections without error."""
    from vector_store.chroma.collection_manager import initialise_all_collections
    collections = initialise_all_collections()
    assert len(collections) == 4
    expected = {
        settings.chroma.collection_candidates,
        settings.chroma.collection_resumes,
        settings.chroma.collection_feedback,
        settings.chroma.collection_interventions,
    }
    assert set(collections.keys()) == expected
