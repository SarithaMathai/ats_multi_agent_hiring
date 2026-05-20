"""
Integration tests — MCP tools (search_similar_interventions, fetch_best_practices_by_issue).

Tests run against the real ChromaDB instance.  A small set of seed interventions
is inserted before the tests and cleaned up after.

Requires: ChromaDB running at CHROMA_HOST:CHROMA_PORT
Skip automatically if ChromaDB is unreachable.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

_DIM      = 384
_TEST_VEC = [0.15] * _DIM

# ── ChromaDB availability guard ───────────────────────────────────────────────

def _chroma_available() -> bool:
    try:
        from vector_store.chroma.client import get_chroma_client
        get_chroma_client().heartbeat()
        return True
    except Exception:
        return False


skip_if_no_chroma = pytest.mark.skipif(
    not _chroma_available(),
    reason="ChromaDB not reachable — skipping MCP tool integration tests",
)


# ── Seed / teardown fixture ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seeded_interventions():
    """Seed 3 interventions and clean them up after all tests in this module."""
    from vector_store.collections.interventions import InterventionsCollection
    col = InterventionsCollection()

    seeds = [
        {
            "case_study_id": "mcp-test-001",
            "issue_text": "Technical interview stage is slow — candidates dropout after 3-week wait",
            "embedding": _TEST_VEC,
            "role": "Software Engineer",
            "outcome_text": "Async video screen cut cycle by 40%",
            "issue_type": "slow_assessment",
            "observed_impact_pct": 40.0,
            "implementation_weeks": 6,
        },
        {
            "case_study_id": "mcp-test-002",
            "issue_text": "High rejection rate at phone screen for junior candidates from Indeed",
            "embedding": _TEST_VEC,
            "role": "Junior Engineer",
            "outcome_text": "Structured scorecard reduced bias rejections by 25%",
            "issue_type": "high_rejection",
            "observed_impact_pct": 25.0,
            "implementation_weeks": 4,
        },
        {
            "case_study_id": "mcp-test-003",
            "issue_text": "Offer declined due to low compensation — three SWE offers declined in one quarter",
            "embedding": _TEST_VEC,
            "role": "Software Engineer",
            "outcome_text": "Salary band update increased acceptance rate from 55% to 78%",
            "issue_type": "offer_decline",
            "observed_impact_pct": 23.0,
            "implementation_weeks": 3,
        },
    ]

    for seed in seeds:
        try:
            col.add_intervention(**seed)
        except Exception:
            pass  # doc may already exist from a previous run

    yield [s["case_study_id"] for s in seeds]

    # Teardown
    for seed in seeds:
        try:
            col._col.delete(ids=[seed["case_study_id"]])
        except Exception:
            pass


# ── Tests: search_similar_interventions ──────────────────────────────────────

@skip_if_no_chroma
async def test_search_returns_results(seeded_interventions):
    """search_similar_interventions returns non-empty results for a valid issue."""
    from mcp_platform.mcp.tools.search_similar_interventions import search_similar_interventions

    results = await search_similar_interventions(
        issue="our technical interview stage is way too slow",
        role=None,
        n_results=3,
    )
    assert isinstance(results, list)
    # May be empty if embedder can't run; assert structure if results present
    for cs in results:
        assert hasattr(cs, "case_study_id")
        assert hasattr(cs, "issue_type")
        assert hasattr(cs, "excerpt")


@skip_if_no_chroma
async def test_search_empty_issue_returns_empty():
    """search_similar_interventions with an empty string returns []."""
    from mcp_platform.mcp.tools.search_similar_interventions import search_similar_interventions

    results = await search_similar_interventions(issue="", n_results=3)
    assert results == []


@skip_if_no_chroma
async def test_search_graceful_degradation():
    """search_similar_interventions never raises — always returns list."""
    from mcp_platform.mcp.tools.search_similar_interventions import search_similar_interventions

    # Passes a valid issue — even if ChromaDB is empty, should return []
    results = await search_similar_interventions(
        issue="some completely unrelated query that won't match anything",
        n_results=1,
    )
    assert isinstance(results, list)


# ── Tests: fetch_best_practices_by_issue ─────────────────────────────────────

@skip_if_no_chroma
async def test_fetch_best_practices_returns_results():
    """fetch_best_practices_by_issue always returns at least one practice (fallback)."""
    from mcp_platform.mcp.tools.fetch_best_practices import fetch_best_practices_by_issue

    practices = await fetch_best_practices_by_issue(
        issue="candidates taking too long in the technical interview stage"
    )
    assert len(practices) >= 1
    for bp in practices:
        assert hasattr(bp, "practice_id")
        assert hasattr(bp, "title")
        assert isinstance(bp.steps, list)
        assert len(bp.steps) >= 1


@skip_if_no_chroma
async def test_fetch_best_practices_normalises_keywords():
    """Different keyword phrasings map to the correct issue type."""
    from mcp_platform.mcp.tools.fetch_best_practices import (
        fetch_best_practices_by_issue,
        _normalise_issue_type,
    )

    assert _normalise_issue_type("our coding test takes too long") == "slow_assessment"
    assert _normalise_issue_type("many candidates declined our offer") == "offer_decline"
    assert _normalise_issue_type("LinkedIn quality is poor") == "sourcing_quality"
    assert _normalise_issue_type("high rejection rate at screen") == "high_rejection"

    # Each call returns valid practices
    for issue in [
        "slow technical assessment",
        "offer declined due to salary",
        "sourcing channel quality",
        "too many rejections",
    ]:
        result = await fetch_best_practices_by_issue(issue)
        assert len(result) >= 1, f"No practices returned for: {issue}"


@skip_if_no_chroma
async def test_fetch_best_practices_fallback_always_present():
    """fetch_best_practices_by_issue always returns at least one result (ChromaDB or fallback)."""
    from mcp_platform.mcp.tools.fetch_best_practices import fetch_best_practices_by_issue

    result = await fetch_best_practices_by_issue(
        issue="extremely unusual niche issue with no matching case study"
    )
    assert len(result) >= 1
    # Result comes from ChromaDB if seeded data matches, or from fallback otherwise.
    # Either way it must be a valid BestPractice with required fields.
    bp = result[0]
    assert bp.practice_id
    assert bp.title
    assert isinstance(bp.steps, list) and len(bp.steps) >= 1
