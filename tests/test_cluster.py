import json
from agentci import cache
from agentci.engineer import cluster

def test_cluster_failures_parses_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    cases = [{"id": "t05", "question": "refund?", "gold": "14 days", "answer": "no refunds"}]
    payload = {"cases": cases}
    result = {"label": "refund-policy", "policy_id": "refund-policy",
              "summary": "drops refund window", "case_ids": ["t05"]}
    (tmp_path / (cache._key("cluster", payload) + ".json")).write_text(json.dumps(result))
    out = cluster.cluster_failures(cases)
    assert out["label"] == "refund-policy"
    assert out["case_ids"] == ["t05"]

def test_cluster_failures_empty_returns_none():
    assert cluster.cluster_failures([]) is None
