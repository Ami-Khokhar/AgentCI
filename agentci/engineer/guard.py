"""Guard runner + two-sided admission test (D15/D16). Assertions are deterministic;
rubric guards are scored by the independent family (D17) through the cache."""
import re


def _run_assertion(check: dict, answer: str) -> dict:
    text = answer or ""
    low = text.lower()
    t = check.get("type")
    if t == "must_include":
        values = check.get("values", [])
        mode = check.get("mode", "all")
        hits = {v: (v.lower() in low) for v in values}
        ok = all(hits.values()) if mode == "all" else any(hits.values())
        missing = [v for v, present in hits.items() if not present]
        return {"passed": ok, "detail": f"missing={missing}" if missing else "all present"}
    if t == "must_cite_policy":
        pid = check.get("policy_id", "")
        ok = pid.lower() in low
        return {"passed": ok, "detail": f"policy {pid} {'cited' if ok else 'absent'}"}
    if t == "regex":
        ok = re.search(check.get("pattern", ""), text) is not None
        return {"passed": ok, "detail": f"regex {'matched' if ok else 'no match'}"}
    raise ValueError(f"unknown assertion check type: {t!r}")


def run_guard(guard: dict, answer: str) -> dict:
    """Execute a guard against an answer -> {'passed': bool, 'detail': str}."""
    if guard["kind"] == "assertion":
        return _run_assertion(guard["check"], answer)
    if guard["kind"] == "rubric":
        from agentci.engineer.independent_judge import score_rubric_guard
        return score_rubric_guard(guard, answer)
    raise ValueError(f"unknown guard kind: {guard['kind']!r}")


def discrimination_test(guard: dict, bad_answer: str, good_answer: str) -> dict:
    """A guard earns admission only if it FAILS on the regressed answer AND PASSES on the
    gold/known-good answer (D15). One-sided guards (loose or over-tight) are rejected."""
    fails_on_bad = not run_guard(guard, bad_answer)["passed"]
    passes_on_good = run_guard(guard, good_answer)["passed"]
    return {
        "admitted": fails_on_bad and passes_on_good,
        "fails_on_bad": fails_on_bad,
        "passes_on_good": passes_on_good,
    }
