import json
from agentci import cache
from agentci.evals import judges

def _seed(tmp_path, dimension, output, expected, kb, policy_id, score):
    payload = {"dimension": dimension, "output": output, "expected": expected,
               "kb": kb, "policy_id": policy_id}
    path = tmp_path / (cache._key("judge", payload) + ".json")
    path.write_text(json.dumps({"score": score, "explanation": "x"}))

def test_correctness_evaluator_returns_cached_score(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    md = {"kb": "KB", "policy_id": "refund-policy"}
    _seed(tmp_path, "correctness", "ans", "gold", "KB", "refund-policy", 0.9)
    score = judges.correctness(output={"answer": "ans"}, expected={"gold_resolution": "gold"}, metadata=md)
    assert score == 0.9

def test_all_four_dimensions_exist():
    assert {f.__name__ for f in judges.ALL_EVALUATORS} == {
        "correctness", "groundedness", "completeness", "policy_reference"}
