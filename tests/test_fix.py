import json
from agentci import cache
from agentci.engineer import fix

def test_draft_fix_parses_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    cluster = {"label": "refund-policy", "policy_id": "refund-policy",
               "summary": "drops refund window", "case_ids": ["t05"]}
    payload = {"candidate_prompt": "SHORT PROMPT", "cluster": cluster}
    result = {"revised_prompt": "SHORT PROMPT + state refund window",
              "rationale": "restores refund detail, keeps brevity"}
    (tmp_path / (cache._key("fix", payload) + ".json")).write_text(json.dumps(result))
    out = fix.draft_fix("SHORT PROMPT", cluster)
    assert "refund" in out["revised_prompt"].lower()
    assert out["rationale"]
