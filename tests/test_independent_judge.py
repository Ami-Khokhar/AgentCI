import json
from agentci import cache
from agentci.engineer.independent_judge import judge_correctness, score_rubric_guard

def test_judge_correctness_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"answer": "A", "gold": "G"}
    (tmp_path / (cache._key("independent_judge", payload) + ".json")).write_text(
        json.dumps({"score": 0.91}))
    assert judge_correctness("A", "G") == 0.91

def test_score_rubric_guard_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    guard = {"kind": "rubric", "slug": "refund-window",
             "rubric_prompt": "PASS iff the answer states the refund window.", "origin": {}}
    payload = {"slug": "refund-window", "rubric_prompt": guard["rubric_prompt"], "answer": "X"}
    (tmp_path / (cache._key("guard_judge", payload) + ".json")).write_text(
        json.dumps({"passed": False, "detail": "no window stated"}))
    r = score_rubric_guard(guard, "X")
    assert r["passed"] is False
