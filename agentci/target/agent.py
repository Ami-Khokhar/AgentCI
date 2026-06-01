"""Factory for the config-driven support agent. A 'candidate' = a different prompt string."""
from google.adk.agents import Agent

from agentci import config
from agentci.target.kb import lookup_kb


def build_support_agent(system_prompt: str | None = None) -> Agent:
    """Build the support-resolution agent with the given system prompt.

    Args:
        system_prompt: The candidate prompt. Defaults to the frozen baseline.
    """
    return Agent(
        name="support_agent",
        model=config.TARGET_MODEL,
        description="Resolves SaaS billing support tickets using the knowledge base.",
        instruction=system_prompt or config.BASELINE_SUPPORT_PROMPT,
        tools=[lookup_kb],
    )
