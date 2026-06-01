from agentci.target.agent import build_support_agent
from agentci import config

def test_agent_uses_given_prompt_and_pinned_model():
    agent = build_support_agent("CUSTOM PROMPT")
    assert agent.instruction == "CUSTOM PROMPT"
    assert agent.model == config.TARGET_MODEL
    tool_names = [getattr(t, "__name__", getattr(t, "name", "")) for t in agent.tools]
    assert "lookup_kb" in tool_names

def test_agent_defaults_to_baseline_prompt():
    agent = build_support_agent()
    assert agent.instruction == config.BASELINE_SUPPORT_PROMPT
