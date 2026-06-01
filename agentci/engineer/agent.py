"""The Engineer agent: an ADK LlmAgent that introspects Phoenix at runtime via MCP (D1)."""
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters

from agentci import config

ENGINEER_INSTRUCTION = """You are AgentCI's reliability engineer. You have Phoenix tools
(via MCP) to read experiments, datasets, traces, and per-case annotations. When asked to
compare a candidate to a baseline, fetch the baseline experiment's per-case scores THROUGH
the Phoenix MCP tools — never assume them. Return structured JSON when asked."""


def phoenix_mcp_server_params() -> StdioServerParameters:
    """Stdio params that launch @arizeai/phoenix-mcp against this Phoenix space."""
    return StdioServerParameters(
        command="npx",
        args=[
            "-y", "@arizeai/phoenix-mcp@latest",
            "--baseUrl", os.environ["PHOENIX_BASE_URL"],
            "--apiKey", os.environ["PHOENIX_API_KEY"],
        ],
    )


def build_engineer_agent() -> LlmAgent:
    """Build the Engineer with the Phoenix MCP server mounted as a toolset (in-process client)."""
    phoenix_tools = McpToolset(
        connection_params=StdioConnectionParams(server_params=phoenix_mcp_server_params())
    )
    return LlmAgent(
        name="agentci_engineer",
        model=config.ENGINEER_MODEL,
        description="Detects regressions, root-causes, and proposes fixes for target agents.",
        instruction=ENGINEER_INSTRUCTION,
        tools=[phoenix_tools],
        # Pin temperature to 0 so the recorded investigation trajectory is deterministic
        # (D7) — matches the target agent; replay then reproduces it exactly.
        generate_content_config=types.GenerateContentConfig(temperature=config.TEMPERATURE),
    )
