"""Quick Day 7 smoke test — run with: .\run.bat scripts\test_day7.py"""
import sys

print("Step 1: agent_selector ...", flush=True)
from agents.routing.agent_selector import agents_for_scenario, default_agents, VALID_SCENARIOS
print(f"  scenarios: {sorted(VALID_SCENARIOS)}", flush=True)
print(f"  default:   {default_agents()}", flush=True)

print("Step 2: RoutingAgent import ...", flush=True)
from agents.routing.routing_agent import RoutingAgent
print("  import OK", flush=True)

print("Step 3: RoutingAgent() ...", flush=True)
agent = RoutingAgent()
print(f"  ready: {agent.agent_name}", flush=True)

print("Step 4: response_assembler ...", flush=True)
from agents.coordinator.response_assembler import assemble_response, CoordinatorResponse
print("  assembler OK", flush=True)

print("Step 5: CoordinatorAgent import ...", flush=True)
from agents.coordinator.coordinator_agent import CoordinatorAgent, PipelineRequest, _AGENT_REGISTRY
print(f"  coordinator OK, registry: {list(_AGENT_REGISTRY.keys())}", flush=True)

print("\nAll Day 7 imports verified.", flush=True)
sys.exit(0)
