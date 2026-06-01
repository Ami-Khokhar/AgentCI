import json
from agentci import cache
from agentci.engineer.investigate import investigate, _parse_investigation

def test_investigate_replays_structured_result(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    result = {"hypothesis": "refund answers omit the window",
              "investigation_steps": ["pulled cand-reg-refund-tune via MCP", "compared to baseline-tune"],
              "root_cause": {"label": "refund-policy", "policy_id": "refund-policy",
                             "summary": "drops the 14-day window", "case_ids": ["t00"]},
              "proposed_fix": {"revised_prompt": "P + state refund window", "rationale": "restores detail"},
              "mcp_calls": 3}
    (tmp_path / (cache._key("investigation", payload) + ".json")).write_text(json.dumps(result))
    out = investigate("P", "reg-refund", ["t00"])
    assert out["root_cause"]["label"] == "refund-policy"
    assert out["mcp_calls"] == 3

def test_parse_investigation_strips_fence():
    raw = "```json\n{\"hypothesis\":\"h\",\"investigation_steps\":[],\"root_cause\":{},\"proposed_fix\":{}}\n```"
    out = _parse_investigation(raw)
    assert out["hypothesis"] == "h"
