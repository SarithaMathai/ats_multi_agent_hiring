# 1. LLMClient
from agents.base.llm_client import LLMClient
client = LLMClient(model="gpt-4o-mini")
print("LLMClient OK  model=%s" % client.model)

# 2. prompt_builder
from agents.base.prompt_builder import build_prompt, ROLE_DESCRIPTIONS
sys_p, usr_p = build_prompt("pipeline_health", "some rag context", "some data", "Why slow?")
assert "pipeline_health" in sys_p
assert "Why slow?" in usr_p
assert len(ROLE_DESCRIPTIONS) == 9
print("prompt_builder OK  roles=%d" % len(ROLE_DESCRIPTIONS))

# 3. output_parser
from agents.base.output_parser import parse_llm_output
from shared.contracts.agent_output import TokenUsage
import json
usage = TokenUsage(input_tokens=10, output_tokens=20)
raw = json.dumps({
    "insights": ["Hiring is slow at technical stage"],
    "recommendations": [{"title": "Fix it", "description": "Speed up assessments", "priority": "high", "effort": "low"}],
    "confidence_score": 0.85
})
out = parse_llm_output(raw, "pipeline_health", [], usage, 150.0)
assert out.status == "success"
assert len(out.insights) == 1
assert out.confidence_score == 0.85
print("output_parser OK  insights=%d recs=%d conf=%.2f" % (len(out.insights), len(out.recommendations), out.confidence_score))

# 4. BaseAgent
from agents.base.base_agent import BaseAgent, AgentContext
from shared.contracts.agent_output import AgentOutput

class TestAgent(BaseAgent):
    agent_name = "test"
    model_tier = "support"
    async def analyse(self, context):
        return AgentOutput.skipped(self.agent_name)

agent = TestAgent()
assert agent.agent_name == "test"
assert agent.model_tier == "support"

ctx_empty = AgentContext(query="test query")
assert agent.build_data_summary(ctx_empty) == "No structured data available."

ctx_data = AgentContext(query="q", structured_data={"candidates": [1, 2, 3], "stages": [1]})
summary = agent.build_data_summary(ctx_data)
assert "candidates: 3 records" in summary
assert "stages: 1 records" in summary
print("BaseAgent OK  agent=%s tier=%s summary=%r" % (agent.agent_name, agent.model_tier, summary))

# 5. run() wraps analyse() with error handling
import asyncio
async def test_run():
    ctx = AgentContext(query="skip me")
    output = await agent.run(ctx)
    assert output.status == "skipped"
    assert output.agent_name == "test"
    print("BaseAgent.run() OK  status=%s" % output.status)

asyncio.run(test_run())

print("ALL DAY 6 CHECKS PASSED")
