from unittest.mock import patch
from agentci import tracing

def test_init_tracing_calls_register_once(monkeypatch):
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "agentci-test")
    tracing._PROVIDER = None  # reset module state
    with patch("agentci.tracing.register") as reg:
        reg.return_value = "provider"
        first = tracing.init_tracing()
        second = tracing.init_tracing()
    assert first == "provider"
    assert second == "provider"
    reg.assert_called_once_with(project_name="agentci-test", auto_instrument=True)
