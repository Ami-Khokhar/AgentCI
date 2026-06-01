from agentci import engineer

def _rows(split, ids, passed):
    # 'answer' is part of the Plan 02 per-case row contract; include it so run_check's
    # answer fallback isn't triggered.
    return [{"id": i, "split": split, "passed": passed, "answer": f"answer-{i}",
             "scores": {"correctness": 0.9 if passed else 0.2, "groundedness": 0.9,
                        "completeness": 0.9, "policy_reference": 0.9}} for i in ids]

def test_benign_candidate_returns_green(monkeypatch):
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], True))
    monkeypatch.setattr(engineer, "run_candidate",
                        lambda prompt, ds, split, name: _rows(split, ["t00"] if split=="tune" else ["h0"], True))
    monkeypatch.setattr(engineer, "_mcp_call_count", lambda: 2)
    report = engineer.run_check("BENIGN PROMPT", "benign-1")
    assert report["verdict"] == "green_no_regression"

def test_regressive_candidate_with_good_fix_promotes(monkeypatch):
    # baseline passes tune but is weak on the held-out case the fix targets, so the
    # fix shows genuine held-out lift; candidate fails t00 (tune) -> regression.
    def fake_run(prompt, ds, split, name):
        if "FIX" in prompt:                       # fixed prompt restores held-out
            return _rows(split, ["t00"] if split=="tune" else ["h0"], True)
        if split == "tune":
            return _rows("tune", ["t00"], False)  # candidate regresses tune
        return _rows("held_out", ["h0"], False)   # candidate also bad on held-out
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], False))
    monkeypatch.setattr(engineer, "run_candidate", fake_run)
    monkeypatch.setattr(engineer, "cluster_failures",
                        lambda cases: {"label": "refund-policy", "policy_id": "refund-policy",
                                       "summary": "s", "case_ids": ["t00"]})
    monkeypatch.setattr(engineer, "draft_fix",
                        lambda p, c: {"revised_prompt": p + " FIX", "rationale": "r"})
    monkeypatch.setattr(engineer, "build_minted_case",
                        lambda cluster, question, gold, index=0: {"id": "minted-x", "split": "tune"})
    monkeypatch.setattr(engineer, "persist_minted_case", lambda case: None)
    monkeypatch.setattr(engineer, "_mcp_call_count", lambda: 4)
    report = engineer.run_check("SHORT PROMPT", "reg-refund")
    assert report["regression_detected"] is True
    assert report["verdict"] == "green_promotable_fix"
