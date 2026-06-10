import json
from agentci import cache
from agentci.engineer.diagnose import diagnose, _parse_json
from agentci.engineer import fix_author
from agentci.engineer.fix_author import author_fix

def test_diagnose_replays_with_guard_and_taxonomy(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    result = {
        "hypothesis": "refund answers omit the window",
        "investigation_steps": ["pulled cand-reg-refund-tune via MCP"],
        "root_cause": {"label": "refund-policy", "policy_id": "R-14",
                       "category": "factual_omission", "summary": "drops the 14-day window",
                       "case_ids": ["t00"]},
        "headline_example": {"id": "t00", "question": "q", "baseline_answer": "14-day window",
                             "candidate_answer": "refunds vary"},
        "guard": {"kind": "assertion", "slug": "refund-window", "claim": "states window",
                  "check": {"type": "must_include", "values": ["14-day"], "mode": "all"},
                  "origin": {"label": "refund-policy", "policy_id": "R-14",
                             "category": "factual_omission", "case_ids": ["t00"]}},
        "mcp_calls": 3,
    }
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(json.dumps(result))
    out = diagnose("P", "reg-refund", ["t00"])
    assert out["root_cause"]["category"] == "factual_omission"
    assert out["guard"]["kind"] == "assertion"
    assert out["mcp_calls"] == 3

def test_author_fix_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    root_cause = {"label": "refund-policy", "summary": "drops the 14-day window"}
    goal = fix_author._FIX_GOAL.format(candidate_prompt="P", root_cause=json.dumps(root_cause),
                                       baseline_prompt="B")
    payload = {"goal": goal}
    (tmp_path / (cache._key("fix", payload) + ".json")).write_text(
        json.dumps({"revised_prompt": "P + state refund window", "rationale": "restores detail"}))
    out = author_fix("P", root_cause, "B")
    assert out["revised_prompt"] == "P + state refund window"

def test_parse_json_strips_fence():
    out = _parse_json("```json\n{\"a\": 1}\n```")
    assert out["a"] == 1


def test_diagnose_empty_lessons_keeps_legacy_cache_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(
        json.dumps({"root_cause": {"category": "factual_omission"}, "guard": {"kind": "assertion"},
                    "mcp_calls": 1}))
    out = diagnose("P", "reg-refund", ["t00"], prior_lessons=[])
    assert out["root_cause"]["category"] == "factual_omission"


def test_diagnose_nonempty_lessons_changes_cache_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    lessons = [{"failure_type": "factual_omission", "lesson": "concise drops citations"}]
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"],
               "prior_lessons": [{"failure_type": "factual_omission", "lesson": "concise drops citations"}]}
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(
        json.dumps({"root_cause": {"category": "factual_omission"}, "guard": {"kind": "assertion"},
                    "mcp_calls": 2}))
    out = diagnose("P", "reg-refund", ["t00"], prior_lessons=lessons)
    assert out["mcp_calls"] == 2
