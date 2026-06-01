from agentci.engineer.compare import compute_flips, is_regression

def _row(id, split, passed, corr=0.9):
    return {"id": id, "split": split, "passed": passed,
            "scores": {"correctness": corr, "groundedness": 0.9,
                       "completeness": 0.9, "policy_reference": 0.9}}

def test_compute_flips_detects_both_directions():
    base = [_row("t00", "tune", True), _row("t01", "tune", False)]
    cand = [_row("t00", "tune", False), _row("t01", "tune", True)]
    flips = compute_flips(base, cand)
    assert flips["pass_to_fail"] == ["t00"]
    assert flips["fail_to_pass"] == ["t01"]

def test_is_regression_true_on_any_tune_pass_to_fail():
    base = [_row("t00", "tune", True)]
    cand = [_row("t00", "tune", False)]
    assert is_regression(base, cand) is True

def test_is_regression_ignores_heldout_flips_for_flagging():
    base = [_row("h0", "held_out", True)]
    cand = [_row("h0", "held_out", False)]
    assert is_regression(base, cand) is False  # flagging is tune-only (D10)
