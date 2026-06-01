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
    report = engineer.run_check("BENIGN PROMPT", "benign-1")
    assert report["verdict"] == "green_no_regression"

def test_regressive_candidate_with_good_fix_proposes_promotable(monkeypatch):
    # baseline passes tune but is weak on the held-out case the fix targets, so the fix
    # shows genuine held-out lift; candidate fails t00 (tune) -> regression.
    def fake_run(prompt, ds, split, name):
        if "FIX" in prompt:
            return _rows(split, ["t00"] if split == "tune" else ["h0"], True)
        if split == "tune":
            return _rows("tune", ["t00"], False)
        return _rows("held_out", ["h0"], False)
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], False))
    monkeypatch.setattr(engineer, "run_candidate", fake_run)
    monkeypatch.setattr(engineer, "investigate", lambda prompt, label, ptf: {
        "hypothesis": "h", "investigation_steps": ["s1"],
        "root_cause": {"label": "refund-policy", "policy_id": "refund-policy", "summary": "s", "case_ids": ["t00"]},
        "proposed_fix": {"revised_prompt": prompt + " FIX", "rationale": "r"}, "mcp_calls": 3})
    monkeypatch.setattr(engineer, "build_minted_case",
                        lambda cluster, question, gold, index=0: {"id": "minted-x", "split": "tune"})
    called = {}
    monkeypatch.setattr(engineer, "persist_minted_case", lambda *a, **k: called.setdefault("persist", True))
    report = engineer.run_check("SHORT PROMPT", "reg-refund")
    assert report["regression_detected"] is True
    assert report["verdict"] == "green_promotable_fix"
    assert report["investigation"]["mcp_calls"] == 3
    assert report["proposed_mint"] == {"id": "minted-x", "split": "tune"}
    assert "persist" not in called  # D12: NOT auto-minted
