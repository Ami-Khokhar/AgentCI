from agentci.engineer import agent as eng
from agentci import config

def test_phoenix_mcp_stdio_params(monkeypatch):
    monkeypatch.setenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com/s/demo")
    monkeypatch.setenv("PHOENIX_API_KEY", "px_live_test")
    params = eng.phoenix_mcp_server_params()
    assert params.command == "npx"
    assert "@arizeai/phoenix-mcp@latest" in params.args
    assert "--baseUrl" in params.args and "https://app.phoenix.arize.com/s/demo" in params.args
    assert "--apiKey" in params.args and "px_live_test" in params.args

def test_engineer_uses_pinned_model_and_mcp_toolset(monkeypatch):
    monkeypatch.setenv("PHOENIX_BASE_URL", "https://x")
    monkeypatch.setenv("PHOENIX_API_KEY", "k")
    a = eng.build_engineer_agent()
    assert a.model == config.ENGINEER_MODEL
    assert len(a.tools) >= 1  # the McpToolset
