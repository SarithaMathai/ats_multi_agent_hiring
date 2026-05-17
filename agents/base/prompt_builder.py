"""
Assembles the system + user prompt for any agent.

All agent prompts share the same structure:
  System prompt:  role declaration + strict JSON output contract
  User prompt:    structured-data summary + RAG evidence + the user query

Agents customise behaviour through their agent_name (determines role description)
and by building a richer data_summary in their analyse() method.
They do NOT subclass PromptBuilder.
"""
from __future__ import annotations

# ── Templates ───────────────────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are the {agent_name} agent in an AI-powered Applicant Tracking System (ATS).

Your role: {role_description}

You MUST respond with a single valid JSON object that matches this schema exactly:
{{
  "insights": [
    "<one clear, specific finding per item — ground every claim in the data>"
  ],
  "recommendations": [
    {{
      "title":       "<short imperative action — max 10 words>",
      "description": "<detailed explanation of what to do and why>",
      "priority":    "high|medium|low",
      "effort":      "low|medium|high"
    }}
  ],
  "confidence_score": <float between 0.0 and 1.0>
}}

Rules:
- Return ONLY the JSON object. No preamble, no trailing text, no markdown fences.
- insights:         3–7 bullet-level findings. Cite numbers from the data where possible.
- recommendations:  2–5 concrete, actionable items ordered by priority.
- confidence_score: 0.85–1.0 = strong evidence; 0.5–0.84 = moderate; below 0.5 = limited data.
- Never invent data. If the provided context is insufficient, say so in insights and set confidence_score low.
"""

_USER_TEMPLATE = """\
## Structured Data Summary
{data_summary}

## Retrieved Context (RAG Evidence)
{rag_context}

## Query
{query}

Analyse the structured data and RAG evidence above. Respond with the JSON object only.
"""

# ── Role descriptions (one per agent name constant) ─────────────────────────────

ROLE_DESCRIPTIONS: dict[str, str] = {
    "coordinator": (
        "Orchestrate the full hiring analysis. Synthesise outputs from all specialist agents "
        "into a coherent executive-level summary with top findings and prioritised recommendations."
    ),
    "routing": (
        "Decide which specialist agents to invoke for this query. Be selective — choose only "
        "the agents whose domain directly addresses the question. Return 2–4 agents at most."
    ),
    "pipeline_health": (
        "Diagnose bottlenecks, stage drop-offs, and stuck candidates in the hiring funnel. "
        "Use stage timing, conversion rates, and duration data to pinpoint exactly where candidates stall."
    ),
    "sourcing_quality": (
        "Evaluate which candidate source channels deliver quality hires and flag channels that "
        "produce high volumes but low pass rates, or that are under-utilised for strong positions."
    ),
    "improvement_action": (
        "Translate rejection patterns and pipeline inefficiencies into prioritised, evidence-backed "
        "corrective actions. Cite specific case studies or best practices from the RAG context."
    ),
    "resource_optimization": (
        "Analyse interviewer workload distribution. Flag panellists who are over-capacity, "
        "identify scheduling gaps, and recommend rebalancing to protect both candidate quality "
        "and interviewer wellbeing."
    ),
    "offer_insights": (
        "Track offer outcomes, acceptance rates, and compensation signals. Identify positions "
        "with declining acceptance or salary misalignment and explain likely root causes."
    ),
    "evaluation": (
        "Review all other agents' outputs for internal consistency, evidence sufficiency, "
        "and realistic confidence scores. Flag any claims that lack supporting data and "
        "downgrade confidence where appropriate."
    ),
    "optimization": (
        "Analyse token usage, API latency, and cost metrics across all agent outputs. "
        "Recommend model tier changes, caching opportunities, or prompt simplifications "
        "that would reduce cost without sacrificing output quality."
    ),
}


# ── Public API ──────────────────────────────────────────────────────────────────

def build_prompt(
    agent_name: str,
    rag_context: str,
    data_summary: str,
    query: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the given agent.

    Args:
        agent_name:   One of the constants from shared.constants.agent_names.
        rag_context:  Pre-formatted string from context_builder (RAG evidence).
        data_summary: Plain-text summary of the structured DB data for this query.
        query:        The user's original question or analysis intent.

    Returns:
        Tuple of (system_prompt, user_prompt) ready for LLMClient.complete().
    """
    role = ROLE_DESCRIPTIONS.get(
        agent_name,
        f"Specialist agent '{agent_name}': provide focused hiring analysis.",
    )

    system = _SYSTEM_TEMPLATE.format(
        agent_name=agent_name,
        role_description=role,
    )
    user = _USER_TEMPLATE.format(
        data_summary=data_summary or "No structured data provided.",
        rag_context=rag_context or "No RAG context available.",
        query=query,
    )
    return system, user
