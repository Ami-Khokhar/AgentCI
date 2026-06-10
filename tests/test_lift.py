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

def test_not_promotable_when_flips_exceed_noise_floor():
    # D8 (amended 2026-06-10): 3 flips > the measured noise floor (2) blocks, even with lift >= 0.
    base = [_r(f"h{i}", True, 0.7) for i in range(4)]
    fixed = ([_r(f"h{i}", False, 0.7) for i in range(3)] + [_r("h3", True, 0.8)])
    out = evaluate_promotion(base, fixed)
    assert out["lift"] >= 0                      # the flip leg, not the lift leg, must block
    assert out["heldout_regressions"] == 3
    assert out["promotable"] is False

def test_promotable_when_flips_within_noise_floor():
    # D8 (amended 2026-06-10): flips at/below the measured baseline-vs-baseline noise floor (2)
    # are sampling noise, not new regressions — they do not block a lift >= 0 recovery.
    base = [_r(f"h{i}", True, 0.7) for i in range(4)]
    fixed = ([_r(f"h{i}", False, 0.6) for i in range(2)] + [_r("h2", True, 0.9), _r("h3", True, 0.9)])
    out = evaluate_promotion(base, fixed)
    assert out["heldout_regressions"] == 2
    assert out["lift"] >= 0
    assert out["promotable"] is True

def test_promotable_at_baseline_parity():
    # D8 (amended): a recovery that matches baseline (lift ~0) with no regressions IS promotable.
    base = [_r("h0", True, 0.80)]
    fixed = [_r("h0", True, 0.82)]   # +0.02 >= 0.0
    out = evaluate_promotion(base, fixed)
    assert out["promotable"] is True

def test_not_promotable_when_below_baseline():
    base = [_r("h0", True, 0.80)]
    fixed = [_r("h0", True, 0.75)]   # -0.05 < 0.0 — fix is worse than production
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
