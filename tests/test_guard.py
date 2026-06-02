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


from agentci.engineer.guard import discrimination_test

def test_discrimination_admits_a_guard_that_fails_bad_passes_good():
    g = _assertion({"type": "must_include", "values": ["14-day"], "mode": "all"})
    res = discrimination_test(g, bad_answer="Refunds vary.", good_answer="A 14-day window applies.")
    assert res["admitted"] is True
    assert res["fails_on_bad"] is True and res["passes_on_good"] is True

def test_discrimination_rejects_guard_that_passes_bad_answer():
    g = _assertion({"type": "must_include", "values": ["refund"], "mode": "all"})
    # 'refund' appears in the bad answer too -> guard cannot tell them apart -> reject
    res = discrimination_test(g, bad_answer="No refund detail.", good_answer="14-day refund window.")
    assert res["admitted"] is False

def test_discrimination_rejects_guard_that_fails_good_answer():
    g = _assertion({"type": "must_include", "values": ["unicorn"], "mode": "all"})
    res = discrimination_test(g, bad_answer="bad", good_answer="14-day refund window.")
    assert res["admitted"] is False and res["passes_on_good"] is False


def test_load_persisted_guards_parses_minted_examples(monkeypatch):
    import agentci.engineer.guard as guardmod
    class FakeDS:
        examples = [
            {"id": "e1", "metadata": {"source": "minted",
                "guard": '{"kind":"assertion","slug":"refund-window","check":{"type":"must_include","values":["14-day"],"mode":"all"},"origin":{}}'}},
            {"id": "e2", "metadata": {"source": "seed"}},  # not a guard
        ]
    monkeypatch.setattr(guardmod, "_get_dataset", lambda name: FakeDS())
    guards = guardmod.load_persisted_guards("ds")
    assert len(guards) == 1
    assert guards[0]["slug"] == "refund-window"
