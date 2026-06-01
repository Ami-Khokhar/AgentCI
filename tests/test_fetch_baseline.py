import json
from agentci import cache
from agentci.engineer import compare

def test_fetch_baseline_parses_mcp_json(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"experiment_name": "baseline-tune"}
    rows = [{"id": "t00", "split": "tune", "passed": True,
             "scores": {"correctness": 0.9, "groundedness": 0.9,
                        "completeness": 0.9, "policy_reference": 0.9}}]
    (tmp_path / (cache._key("mcp_baseline", payload) + ".json")).write_text(json.dumps(rows))
    out = compare.fetch_baseline_via_mcp("baseline-tune")
    assert out == rows
