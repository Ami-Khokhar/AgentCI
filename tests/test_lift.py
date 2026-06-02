from agentci.engineer.lift import mean_correctness, evaluate_promotion

def _r(id, passed, corr):
    return {"id": id, "split": "held_out", "passed": passed,
            "scores": {"correctness": corr, "groundedness": 0.9,
                       "completeness": 0.9, "policy_reference": 0.9}}

def test_mean_correctness():
    assert mean_correctness([_r("h0", True, 0.8), _r("h1", True, 0.6)]) == 0.7

def test_promotable_when_lift_and_no_regressions():
    base = [_r("h0", True, 0.6), _r("h1", True, 0.6)]
    fixed = [_r("h0", True, 0.9), _r("h1", True, 0.9)]
    out = evaluate_promotion(base, fixed)
    assert out["lift"] == 0.3 and out["heldout_regressions"] == 0
    assert out["promotable"] is True and out["n"] == 2

def test_not_promotable_when_heldout_regression():
    base = [_r("h0", True, 0.9)]
    fixed = [_r("h0", False, 0.4)]   # pass->fail on held-out
    out = evaluate_promotion(base, fixed)
    assert out["heldout_regressions"] == 1
    assert out["promotable"] is False

def test_not_promotable_when_lift_too_small():
    base = [_r("h0", True, 0.80)]
    fixed = [_r("h0", True, 0.82)]   # +0.02 < 0.05
    out = evaluate_promotion(base, fixed)
    assert out["promotable"] is False


from agentci.engineer.lift import attach_independent_correctness

def test_attach_independent_correctness_overwrites_with_ruler(monkeypatch):
    import agentci.engineer.lift as lift
    monkeypatch.setattr(lift, "judge_correctness", lambda answer, gold: 0.95)
    rows = [{"id": "h0", "split": "held_out", "answer": "A",
             "scores": {"correctness": 0.40}, "passed": False}]
    gold_by_id = {"h0": "G"}
    out = attach_independent_correctness(rows, gold_by_id)
    # independent ruler replaces the in-family correctness used for lift
    assert out[0]["scores"]["correctness"] == 0.95
