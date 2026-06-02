from agentci.engineer.guard import run_guard

def _assertion(check):
    return {"kind": "assertion", "slug": "refund-window", "claim": "states refund window",
            "check": check, "origin": {}}

def test_must_include_all_passes_when_all_present():
    g = _assertion({"type": "must_include", "values": ["14-day", "eligibility"], "mode": "all"})
    r = run_guard(g, "Our 14-day window applies; see eligibility terms.")
    assert r["passed"] is True

def test_must_include_all_fails_when_one_missing():
    g = _assertion({"type": "must_include", "values": ["14-day", "eligibility"], "mode": "all"})
    r = run_guard(g, "Refunds are handled case by case.")
    assert r["passed"] is False
    assert "14-day" in r["detail"]

def test_must_cite_policy_checks_policy_id_presence():
    g = _assertion({"type": "must_cite_policy", "policy_id": "R-14"})
    assert run_guard(g, "Per policy R-14 you qualify.")["passed"] is True
    assert run_guard(g, "You qualify.")["passed"] is False

def test_regex_assertion():
    g = _assertion({"type": "regex", "pattern": r"\b\d+\s*day"})
    assert run_guard(g, "a 14 day window")["passed"] is True
    assert run_guard(g, "no window stated")["passed"] is False
