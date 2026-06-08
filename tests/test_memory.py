import json

import pytest

from agentci.memory import memory


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))


def test_load_empty_when_missing():
    assert memory.load_memory() == []


def test_append_round_trip():
    memory.append_entry({"failure_type": "factual_omission", "lesson": "L"})
    memory.append_entry({"failure_type": "over_refusal", "lesson": "M"})
    out = memory.load_memory()
    assert [e["lesson"] for e in out] == ["L", "M"]


def test_find_relevant_matches_by_policy(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case",
                        lambda: {"t-refund": "refund-policy", "t-other": "login"})
    memory.append_entry({"failure_type": "factual_omission", "lesson": "concise drops citations",
                         "affected_policies": ["refund-policy"]})
    memory.append_entry({"failure_type": "format_regression", "lesson": "unrelated",
                         "affected_policies": ["billing"]})
    hits = memory.find_relevant(["t-refund"])
    assert len(hits) == 1 and hits[0]["lesson"] == "concise drops citations"


def test_find_relevant_empty_for_no_flips():
    assert memory.find_relevant([]) == []


def test_format_for_prompt_empty_is_blank():
    assert memory.format_for_prompt([]) == ""


def test_format_for_prompt_renders_lessons():
    txt = memory.format_for_prompt([{"failure_type": "factual_omission",
                                     "lesson": "concise drops citations",
                                     "successful_fix": "force citation"}])
    assert "factual_omission" in txt and "concise drops citations" in txt


def test_build_entry_maps_report_fields(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case", lambda: {"t05": "refund-policy"})
    report = {
        "candidate_label": "reg-concise",
        "flips": {"pass_to_fail": ["t05"], "fail_to_pass": []},
        "investigation": {"root_cause": {"category": "factual_omission", "policy_id": "refund-policy",
                                          "summary": "dropped the 14-day window"}},
        "proposed_fix": {"rationale": "always cite refund policy"},
        "proposed_mint": {"id": "minted-refund-policy-0",
                          "guard": '{"slug": "refund-window"}'},
    }
    e = memory.build_entry(report, timestamp="2026-06-08T00:00:00+00:00")
    assert e["failure_type"] == "factual_omission"
    assert e["triggering_prompt_change"] == "reg-concise"
    assert e["root_cause"] == "dropped the 14-day window"
    assert e["affected_cases"] == ["t05"]
    assert e["affected_policies"] == ["refund-policy"]
    assert e["successful_fix"] == "always cite refund policy"
    assert e["failed_fixes"] == []
    assert e["new_eval_cases"] == {"id": "minted-refund-policy-0", "guard_slug": "refund-window"}
    assert e["approval_status"] == "approved"
    assert e["timestamp"] == "2026-06-08T00:00:00+00:00"
    assert e["lesson"] == memory._LESSON_TEMPLATES["factual_omission"]


def test_find_relevant_unknown_ids_returns_empty(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case", lambda: {"t-refund": "refund-policy"})
    memory.append_entry({"failure_type": "factual_omission", "lesson": "L",
                         "affected_policies": ["refund-policy"]})
    assert memory.find_relevant(["t-unknown"]) == []


def test_record_approval_appends_and_returns(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case", lambda: {"t05": "refund-policy"})
    report = {"candidate_label": "reg-concise",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "r"},
              "proposed_mint": {"id": "minted-0", "guard": "{}"}}
    entry = memory.record_approval(report, timestamp="2026-06-08T00:00:00+00:00")
    assert entry["failure_type"] == "factual_omission"
    assert memory.load_memory() == [entry]
