from agents.base.llm_client import LLMClient
client = LLMClient(model="gpt-4o-mini")
print("LLM client initialised:", client.model)
