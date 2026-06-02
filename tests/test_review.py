import json
from agentci import cache
from agentci.engineer.review import review_rubric, passes_review

def test_review_rubric_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    guard = {"kind": "rubric", "slug": "refund-window",
             "rubric_prompt": "PASS iff the answer states the refund window.", "origin": {}}
    payload = {"slug": "refund-window", "rubric_prompt": guard["rubric_prompt"]}
    (tmp_path / (cache._key("guard_review", payload) + ".json")).write_text(
        json.dumps({"score": 0.85, "notes": "specific, not gameable"}))
    out = review_rubric(guard)
    assert out["score"] == 0.85
    assert passes_review(out) is True

def test_passes_review_below_threshold():
    assert passes_review({"score": 0.4, "notes": "too vague"}) is False
