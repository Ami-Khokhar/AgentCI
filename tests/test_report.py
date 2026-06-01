from agentci.engineer.report import assemble_report

def test_green_when_no_regression():
    r = assemble_report(candidate_label="benign-1", regression=False,
                        flips={"pass_to_fail": [], "fail_to_pass": []},
                        cluster=None, fix=None, promotion=None, mcp_calls=3)
    assert r["verdict"] == "green_no_regression"
    assert r["gate"] == "green"

def test_green_when_fix_promotable():
    r = assemble_report(candidate_label="reg-refund", regression=True,
                        flips={"pass_to_fail": ["t05"], "fail_to_pass": []},
                        cluster={"label": "refund-policy"},
                        fix={"revised_prompt": "p", "rationale": "r"},
                        promotion={"promotable": True, "lift": 0.2, "n": 16,
                                   "heldout_regressions": 0, "reason": "ok"},
                        mcp_calls=5)
    assert r["verdict"] == "green_promotable_fix"
    assert r["gate"] == "green"

def test_red_when_no_qualifying_fix():
    r = assemble_report(candidate_label="reg-hard", regression=True,
                        flips={"pass_to_fail": ["t09"], "fail_to_pass": []},
                        cluster={"label": "x"},
                        fix={"revised_prompt": "p", "rationale": "r"},
                        promotion={"promotable": False, "lift": 0.01, "n": 16,
                                   "heldout_regressions": 0, "reason": "insufficient"},
                        mcp_calls=5)
    assert r["verdict"] == "red_no_fix"
    assert r["gate"] == "red"

def test_report_carries_investigation_and_proposed_mint():
    r = assemble_report("reg", True, {"pass_to_fail": ["t0"], "fail_to_pass": []},
                        {"label": "x"}, {"revised_prompt": "p", "rationale": "r"},
                        {"promotable": True, "lift": 0.2, "n": 16, "heldout_regressions": 0, "reason": "ok"},
                        5, investigation={"hypothesis": "h", "mcp_calls": 5}, proposed_mint={"id": "minted-x"})
    assert r["investigation"]["hypothesis"] == "h"
    assert r["proposed_mint"]["id"] == "minted-x"
    assert r["verdict"] == "green_promotable_fix"
