from agentci import engineer

def _rows(split, ids, passed):
    return [{"id": i, "split": split, "passed": passed, "answer": f"answer-{i}",
             "scores": {"correctness": 0.9 if passed else 0.2, "groundedness": 0.9,
                        "completeness": 0.9, "policy_reference": 0.9}} for i in ids]

def test_benign_candidate_returns_green(monkeypatch):
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], True))
    monkeypatch.setattr(engineer, "run_candidate",
                        lambda prompt, ds, split, name: _rows(split, ["t00"] if split == "tune" else ["h0"], True))
    monkeypatch.setattr(engineer, "load_persisted_guards", lambda ds: [])
    report = engineer.run_check("BENIGN PROMPT", "benign-1")
    assert report["verdict"] == "green_no_regression"

def test_persisted_guard_trip_blocks_immediately(monkeypatch):
    # A persisted guard that the candidate's answer fails -> instant guard_blocked, no investigation.
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], True))
    monkeypatch.setattr(engineer, "run_candidate",
                        lambda prompt, ds, split, name: _rows(split, ["t00"] if split == "tune" else ["h0"], True))
    guard = {"kind": "assertion", "slug": "refund-window", "claim": "states window",
             "check": {"type": "must_include", "values": ["14-day"], "mode": "all"},
             "origin": {"label": "refund-policy"}}
    monkeypatch.setattr(engineer, "load_persisted_guards", lambda ds: [guard])
    # candidate answers (answer-t00) omit '14-day' -> guard trips
    report = engineer.run_check("SHORT PROMPT", "reg-refund-2")
    assert report["verdict"] == "guard_blocked"
    assert report["guard_gate"]["tripped"] is True
    assert report["guard_gate"]["guard"]["slug"] == "refund-window"

def test_regression_with_admitted_guard_and_good_fix(monkeypatch):
    def fake_run(prompt, ds, split, name):
        if "FIX" in prompt:
            return _rows(split, ["t00"] if split == "tune" else ["h0"], True)
        return _rows("tune", ["t00"], False) if split == "tune" else _rows("held_out", ["h0"], False)
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], False))
    monkeypatch.setattr(engineer, "run_candidate", fake_run)
    monkeypatch.setattr(engineer, "load_persisted_guards", lambda ds: [])  # no prior guards
    monkeypatch.setattr(engineer, "diagnose", lambda prompt, label, ptf: {
        "hypothesis": "h", "investigation_steps": ["s1"],
        "root_cause": {"label": "refund-policy", "policy_id": "R-14", "category": "factual_omission",
                       "summary": "drops window", "case_ids": ["t00"]},
        "headline_example": {"id": "t00", "question": "q", "baseline_answer": "14-day window",
                             "candidate_answer": "refunds vary"},
        "guard": {"kind": "assertion", "slug": "refund-window", "claim": "states window",
                  "check": {"type": "must_include", "values": ["14-day"], "mode": "all"},
                  "origin": {"label": "refund-policy"}},
        "mcp_calls": 3})
    monkeypatch.setattr(engineer, "author_fix",
                        lambda prompt, rc: {"revised_prompt": prompt + " FIX", "rationale": "r"})
    # discrimination: guard fails on candidate's wrong answer, passes on the gold answer
    monkeypatch.setattr(engineer, "discrimination_test",
                        lambda g, bad_answer, good_answer: {"admitted": True, "fails_on_bad": True, "passes_on_good": True})
    monkeypatch.setattr(engineer, "attach_independent_correctness", lambda rows, gold: rows)
    monkeypatch.setattr(engineer, "build_minted_case",
                        lambda cluster, q, gold, index=0, guard=None: {"id": "minted-x", "split": "tune", "guard": "{}"})
    report = engineer.run_check("SHORT PROMPT", "reg-refund")
    assert report["verdict"] == "green_promotable_fix"
    assert report["proposed_guard"]["admitted"] is True
    assert report["proposed_mint"]["id"] == "minted-x"
