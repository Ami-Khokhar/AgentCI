# Compounding Regression Immunity — Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the gate goes red, the investigator authors a validated, targeted guard (deterministic assertion and/or scoped LLM-judge rubric); on approval the guard joins the permanent suite and blocks that exact regression forever, with improvement proven on a frozen cross-family ruler.

**Architecture:** Deterministic CI scaffolding (`run_check`) wraps agentic steps. New: a guard runner + two-sided discrimination test, an independent-family correctness judge for the held-out lift gate, an adversarial rubric reviewer, a diagnose/fix-author split, and a persisted-guard gate that hard-blocks repeat regressions. Every LLM-touching call is wrapped in `cache.cached(...)` and replay-seeded in tests — no network, no asserting on model text.

**Tech Stack:** Python 3.14 via `uv`; Google ADK + `google-genai` (target, investigator, fix-author); `anthropic` (independent-family judge + reviewer); `arize-phoenix-client` (dataset/experiments); pytest + pytest-asyncio.

**Scope note:** This plan delivers the engine + report contract. Dashboard meta-metrics surfacing (spec §5.10) and the cheap-screener (spec §5.9) are deferred to Plan 07 (the surface), which depends on this plan landing first.

**Reference spec:** `docs/superpowers/specs/2026-06-02-compounding-immunity-design.md`

---

## File Structure

- **Modify** `docs/superpowers/plans/2026-06-01-agentci-00-overview.md` — append D15–D19 (decision table is the contract; update before code).
- **Modify** `agentci/config.py` — add `IMPROVEMENT_JUDGE_MODEL`, `GUARD_REVIEWER_MODEL`, `FAILURE_TAXONOMY`, `GUARD_REVIEW_THRESHOLD`, `GUARD_REFINE_ATTEMPTS`.
- **Modify** `pyproject.toml` — add `anthropic` dependency.
- **Create** `agentci/engineer/guard.py` — guard data shape, `run_guard`, `discrimination_test`, `load_persisted_guards`.
- **Create** `agentci/engineer/independent_judge.py` — cross-family correctness judge (`judge_correctness`, `score_independent`) and the rubric-guard scorer used by `guard.py`.
- **Create** `agentci/engineer/review.py` — `review_rubric` adversarial reviewer (independent family).
- **Create** `agentci/engineer/diagnose.py` — `diagnose()` (renamed/expanded from `investigate`): root cause + taxonomy + headline + authored guard. No fix.
- **Create** `agentci/engineer/fix_author.py` — `author_fix()`: separate agent that writes the proposed prompt fix (D19).
- **Modify** `agentci/engineer/lift.py` — `evaluate_promotion` uses the independent correctness score (D17).
- **Modify** `agentci/engineer/mint.py` — `build_minted_case` + `persist_minted_case` carry the guard spec.
- **Modify** `agentci/engineer/report.py` — add `guard_gate`, `proposed_guard`, `guard_review`, `verdict="guard_blocked"`.
- **Modify** `agentci/engineer/__init__.py` — orchestrate the new loop; import new fns into the package namespace so tests can monkeypatch them.
- **Delete** `agentci/engineer/investigate.py` after `diagnose.py` + `fix_author.py` replace it (keep its replay fixtures' structure in mind).
- **Tests** under `tests/` mirror each module.

---

## Task 0: Append decisions D15–D19 to the overview

**Files:**
- Modify: `docs/superpowers/plans/2026-06-01-agentci-00-overview.md` (after the `| D14 | ... |` row)

- [ ] **Step 1: Append the five decision rows**

Add these rows immediately after the D14 row (match the existing `| Dn | **Title** | desc |` format):

```markdown
| D15 | **Agent-authored guards** | Guards are agent-authored, hybrid (`assertion`\|`rubric`), and admitted only via a two-sided discrimination test: the guard must FAIL on the regressed answer and PASS on the gold answer. |
| D16 | **Guard gate (behavior C)** | Tripping a persisted guard is an instant RED plus investigator narration of which learned guard tripped and its origin run. Independent of flip detection. |
| D17 | **Frozen cross-family improvement ruler** | Held-out correctness lift (D8) is scored by `IMPROVEMENT_JUDGE_MODEL`, a non-Gemini family distinct from `ENGINEER_MODEL`. The agent cannot grade its own homework. |
| D18 | **Independent guard review** | Rubric guards are reviewed by `GUARD_REVIEWER_MODEL` (independent family) for specificity, gameability, and over-constraint before admission. |
| D19 | **Diagnose/fix split** | Diagnosis (+ guard authoring) and fix-authoring are separate agents (Engine's lesson: one agent doing both degrades quality). |
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-agentci-00-overview.md docs/superpowers/specs/2026-06-02-compounding-immunity-design.md
git commit -m "docs: add D15-D19 + compounding-immunity spec"
```

---

## Task 1: Config additions

**Files:**
- Modify: `agentci/config.py`
- Modify: `pyproject.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_improvement_judge_is_independent_family():
    from agentci import config
    # D17: the improvement ruler must NOT share a family with the optimizer.
    assert config.IMPROVEMENT_JUDGE_MODEL != config.ENGINEER_MODEL
    assert not config.IMPROVEMENT_JUDGE_MODEL.startswith("gemini")
    assert not config.GUARD_REVIEWER_MODEL.startswith("gemini")

def test_failure_taxonomy_is_fixed_set():
    from agentci import config
    assert "factual_omission" in config.FAILURE_TAXONOMY
    assert "over_refusal" in config.FAILURE_TAXONOMY
    assert len(config.FAILURE_TAXONOMY) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: module 'agentci.config' has no attribute 'IMPROVEMENT_JUDGE_MODEL'`

- [ ] **Step 3: Add the config**

Append to `agentci/config.py`:

```python
# --- Cross-family independence (D17/D18): the ruler must not share a brain with the optimizer ---
IMPROVEMENT_JUDGE_MODEL = "claude-haiku-4-5-20251001"   # frozen held-out correctness ruler
GUARD_REVIEWER_MODEL = "claude-haiku-4-5-20251001"      # adversarial rubric reviewer

# --- Guard authoring/admission (D15/D18) ---
FAILURE_TAXONOMY = (
    "factual_omission", "over_refusal", "policy_miscite",
    "hallucination", "format_regression",
)
GUARD_REVIEW_THRESHOLD = 0.7    # rubric reviewer score >= this to admit
GUARD_REFINE_ATTEMPTS = 2       # how many times the agent may refine a rejected guard
```

- [ ] **Step 4: Add the dependency**

In `pyproject.toml`, add `"anthropic>=0.40"` to the `[project] dependencies` list (the independent-family judge calls it only on the live/record path; replay never imports it).

- [ ] **Step 5: Run tests + sync**

Run: `uv sync && uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agentci/config.py pyproject.toml uv.lock tests/test_config.py
git commit -m "feat: cross-family judge config + failure taxonomy (D17/D18)"
```

---

## Task 2: Guard runner — deterministic assertion kind

**Files:**
- Create: `agentci/engineer/guard.py`
- Test: `tests/test_guard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_guard.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.guard'`

- [ ] **Step 3: Write the assertion runner**

Create `agentci/engineer/guard.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_guard.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/guard.py tests/test_guard.py
git commit -m "feat: deterministic assertion guard runner (D15)"
```

---

## Task 3: Independent-family judge + rubric-guard scoring

**Files:**
- Create: `agentci/engineer/independent_judge.py`
- Test: `tests/test_independent_judge.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_independent_judge.py`:

```python
import json
from agentci import cache
from agentci.engineer.independent_judge import judge_correctness, score_rubric_guard

def test_judge_correctness_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"answer": "A", "gold": "G"}
    (tmp_path / (cache._key("independent_judge", payload) + ".json")).write_text(
        json.dumps({"score": 0.91}))
    assert judge_correctness("A", "G") == 0.91

def test_score_rubric_guard_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    guard = {"kind": "rubric", "slug": "refund-window",
             "rubric_prompt": "PASS iff the answer states the refund window.", "origin": {}}
    payload = {"slug": "refund-window", "rubric_prompt": guard["rubric_prompt"], "answer": "X"}
    (tmp_path / (cache._key("guard_judge", payload) + ".json")).write_text(
        json.dumps({"passed": False, "detail": "no window stated"}))
    r = score_rubric_guard(guard, "X")
    assert r["passed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_independent_judge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.independent_judge'`

- [ ] **Step 3: Write the module**

Create `agentci/engineer/independent_judge.py`:

```python
"""Cross-family judge (D17): a non-Gemini model scores held-out correctness and rubric guards,
so the ruler never shares a brain with the Gemini investigator/fix-author. Cached (D7)."""
import json

from agentci import cache, config


def _anthropic_json(prompt: str, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model, max_tokens=512, temperature=config.TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def judge_correctness(answer: str, gold: str) -> float:
    """Independent-family correctness score in [0,1] for held-out lift (D17). Cached."""
    payload = {"answer": answer, "gold": gold}

    def live():
        prompt = (
            "You are a strict, independent evaluator. Score how well the ANSWER matches the "
            "GOLD resolution in substance: 1.0 = fully correct, 0.0 = wrong or contradictory.\n\n"
            f"GOLD:\n{gold}\n\nANSWER:\n{answer}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>}'
        )
        data = _anthropic_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
        return {"score": max(0.0, min(1.0, float(data.get("score", 0.0))))}

    return cache.cached("independent_judge", payload, live)["score"]


def score_rubric_guard(guard: dict, answer: str) -> dict:
    """Score a rubric guard against an answer on the independent family. Cached."""
    payload = {"slug": guard["slug"], "rubric_prompt": guard["rubric_prompt"], "answer": answer}

    def live():
        prompt = (
            "You are a strict guard. Apply this PASS/FAIL rubric to the ANSWER.\n\n"
            f"RUBRIC: {guard['rubric_prompt']}\n\nANSWER:\n{answer}\n\n"
            'Return ONLY JSON: {"passed": <true|false>, "detail": "<one sentence>"}'
        )
        data = _anthropic_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
        return {"passed": bool(data.get("passed", False)), "detail": str(data.get("detail", ""))}

    return cache.cached("guard_judge", payload, live)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_independent_judge.py tests/test_guard.py -v`
Expected: PASS (both files; rubric path in guard.py now resolves)

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/independent_judge.py tests/test_independent_judge.py
git commit -m "feat: independent-family judge for held-out lift + rubric guards (D17)"
```

---

## Task 4: Guard discrimination test (two-sided admission)

**Files:**
- Modify: `agentci/engineer/guard.py`
- Test: `tests/test_guard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_guard.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_guard.py::test_discrimination_admits_a_guard_that_fails_bad_passes_good -v`
Expected: FAIL with `ImportError: cannot import name 'discrimination_test'`

- [ ] **Step 3: Implement discrimination_test**

Append to `agentci/engineer/guard.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_guard.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/guard.py tests/test_guard.py
git commit -m "feat: two-sided guard discrimination test (D15)"
```

---

## Task 5: Held-out lift uses the independent ruler (D17)

**Files:**
- Modify: `agentci/engineer/lift.py`
- Test: `tests/test_lift.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lift.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lift.py::test_attach_independent_correctness_overwrites_with_ruler -v`
Expected: FAIL with `ImportError: cannot import name 'attach_independent_correctness'`

- [ ] **Step 3: Implement the re-scoring helper**

In `agentci/engineer/lift.py`, add the import at the top (below the existing imports):

```python
from agentci.engineer.independent_judge import judge_correctness
```

Then append:

```python
def attach_independent_correctness(rows: list[dict], gold_by_id: dict[str, str]) -> list[dict]:
    """Re-score each row's correctness with the independent-family ruler (D17), so the held-out
    lift gate measures improvement on a brain the optimizer does not control. Returns new rows."""
    out = []
    for r in rows:
        row = dict(r)
        row["scores"] = dict(r["scores"])
        gold = gold_by_id.get(r["id"], "")
        row["scores"]["correctness"] = judge_correctness(r.get("answer", ""), gold)
        out.append(row)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_lift.py -v`
Expected: PASS (existing + new). `evaluate_promotion` already reads `scores["correctness"]`, so re-scored rows flow straight into the gate.

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/lift.py tests/test_lift.py
git commit -m "feat: held-out lift scored by independent-family ruler (D17)"
```

---

## Task 6: Adversarial rubric reviewer (D18)

**Files:**
- Create: `agentci/engineer/review.py`
- Test: `tests/test_review.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_review.py`:

```python
import json
from agentci import cache
from agentci.engineer.review import review_rubric, passes_review

def test_review_rubric_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    guard = {"kind": "rubric", "slug": "refund-window",
             "rubric_prompt": "PASS iff the answer states the refund window.", "origin": {}}
    payload = {"slug": "refund-window", "rubric_prompt": guard["rubric_prompt"]}
    (tmp_path / (cache._key("guard_review", payload) + ".json")).write_text(
        json.dumps({"score": 0.85, "notes": "specific, not gameable"}))
    out = review_rubric(guard)
    assert out["score"] == 0.85
    assert passes_review(out) is True

def test_passes_review_below_threshold():
    assert passes_review({"score": 0.4, "notes": "too vague"}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_review.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.review'`

- [ ] **Step 3: Implement the reviewer**

Create `agentci/engineer/review.py`:

```python
"""Adversarial rubric review (D18): an independent-family model judges whether a rubric guard is
specific, non-gameable, and not over-constrained. Only applies to kind='rubric'. Cached (D7)."""
from agentci import cache, config
from agentci.engineer.independent_judge import _anthropic_json


def review_rubric(guard: dict) -> dict:
    """Score a rubric guard's quality in [0,1]. Cached."""
    payload = {"slug": guard["slug"], "rubric_prompt": guard["rubric_prompt"]}

    def live():
        prompt = (
            "You review proposed regression-test rubrics. Score this rubric 0..1 on: is it "
            "SPECIFIC to one failure (not generic), is it NOT trivially gameable, and is it NOT "
            "over-constrained (would not reject a correct answer phrased differently). "
            "Low score if it fails any.\n\n"
            f"RUBRIC: {guard['rubric_prompt']}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>, "notes": "<one sentence>"}'
        )
        data = _anthropic_json(prompt, config.GUARD_REVIEWER_MODEL)
        return {"score": max(0.0, min(1.0, float(data.get("score", 0.0)))),
                "notes": str(data.get("notes", ""))}

    return cache.cached("guard_review", payload, live)


def passes_review(review: dict) -> bool:
    return review.get("score", 0.0) >= config.GUARD_REVIEW_THRESHOLD
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_review.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/review.py tests/test_review.py
git commit -m "feat: adversarial rubric reviewer, independent family (D18)"
```

---

## Task 7: Split investigate into diagnose() + author_fix() (D19)

**Files:**
- Create: `agentci/engineer/diagnose.py`
- Create: `agentci/engineer/fix_author.py`
- Delete: `agentci/engineer/investigate.py`
- Test: `tests/test_diagnose.py` (new), update `tests/test_investigate.py` → rename to `tests/test_diagnose.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_diagnose.py` (replaces `tests/test_investigate.py`):

```python
import json
from agentci import cache
from agentci.engineer.diagnose import diagnose, _parse_json
from agentci.engineer.fix_author import author_fix

def test_diagnose_replays_with_guard_and_taxonomy(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    result = {
        "hypothesis": "refund answers omit the window",
        "investigation_steps": ["pulled cand-reg-refund-tune via MCP"],
        "root_cause": {"label": "refund-policy", "policy_id": "R-14",
                       "category": "factual_omission", "summary": "drops the 14-day window",
                       "case_ids": ["t00"]},
        "headline_example": {"id": "t00", "question": "q", "baseline_answer": "14-day window",
                             "candidate_answer": "refunds vary"},
        "guard": {"kind": "assertion", "slug": "refund-window", "claim": "states window",
                  "check": {"type": "must_include", "values": ["14-day"], "mode": "all"},
                  "origin": {"label": "refund-policy", "policy_id": "R-14",
                             "category": "factual_omission", "case_ids": ["t00"]}},
        "mcp_calls": 3,
    }
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(json.dumps(result))
    out = diagnose("P", "reg-refund", ["t00"])
    assert out["root_cause"]["category"] == "factual_omission"
    assert out["guard"]["kind"] == "assertion"
    assert out["mcp_calls"] == 3

def test_author_fix_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    root_cause = {"label": "refund-policy", "summary": "drops the 14-day window"}
    payload = {"candidate_prompt": "P", "root_cause": root_cause}
    (tmp_path / (cache._key("fix", payload) + ".json")).write_text(
        json.dumps({"revised_prompt": "P + state refund window", "rationale": "restores detail"}))
    out = author_fix("P", root_cause)
    assert out["revised_prompt"] == "P + state refund window"

def test_parse_json_strips_fence():
    out = _parse_json("```json\n{\"a\": 1}\n```")
    assert out["a"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_diagnose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.diagnose'`

- [ ] **Step 3: Write diagnose.py**

Create `agentci/engineer/diagnose.py` (adapted from the old `investigate.py`; the agent now also classifies into the taxonomy and authors the guard, and NO LONGER proposes the fix — D19):

```python
"""Agentic diagnosis (D11/D15/D19): a Gemini reason-act loop over Phoenix MCP that root-causes
the regression, classifies it into the fixed taxonomy, and AUTHORS a guard. It does NOT write the
fix (that is a separate agent, D19). Cached (D7) so the demo replays the captured trajectory."""
import asyncio
import json
import uuid

from agentci import cache, config

_DIAGNOSIS_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped PASS->FAIL versus baseline: {pass_to_fail}.

Investigate WHY, like a reliability engineer. Use your Phoenix MCP tools to pull the candidate
experiment ('cand-{label}-tune'), the baseline ('baseline-tune'), and per-case annotations/traces
for the flipped cases. Form a hypothesis, verify it holds across the flipped cases and is absent
from still-passing ones, and refine.

Classify the root cause into EXACTLY ONE category from: {taxonomy}.

Then AUTHOR A GUARD — a regression test that asserts the specific property a correct answer must
satisfy. Prefer a deterministic 'assertion' when the property is crisp (a required phrase, a cited
policy id, a number); use a scoped 'rubric' (a one-line PASS/FAIL LLM-judge prompt) when the
property is semantic. The guard must be specific to THIS failure, not generic.

Also surface the single most telling flipped case as a side-by-side (question, baseline correct
answer, candidate wrong answer), pulled from traces via MCP.

Return ONLY JSON:
{{"hypothesis":"<...>",
  "investigation_steps":["<each MCP query/check, in order>"],
  "root_cause":{{"label":"<short>","policy_id":"<kb id>","category":"<one taxonomy value>","summary":"<one sentence>","case_ids":["..."]}},
  "headline_example":{{"id":"<case id>","question":"<ticket>","baseline_answer":"<correct>","candidate_answer":"<wrong>"}},
  "guard":{{"kind":"assertion|rubric","slug":"<kebab>","claim":"<property a correct answer must satisfy>","check":{{"type":"must_include|must_cite_policy|regex","values":["..."],"mode":"all|any","policy_id":"<id>","pattern":"<re>"}},"rubric_prompt":"<only if kind=rubric>","origin":{{"label":"<>","policy_id":"<>","category":"<>","case_ids":["..."]}}}}}}"""


def _parse_json(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_diagnosis(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> tuple[str, int]:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-diagnose")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(app_name="agentci-diagnose", user_id=uid, session_id=sid)
    goal = _DIAGNOSIS_GOAL.format(
        label=label, pass_to_fail=pass_to_fail,
        taxonomy=", ".join(config.FAILURE_TAXONOMY),
    )
    final, mcp_calls = "", 0
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=goal)]),
    ):
        fcs = event.get_function_calls() if hasattr(event, "get_function_calls") else None
        if fcs:
            mcp_calls += len(fcs)
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final, mcp_calls


def diagnose(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> dict:
    """Root cause + taxonomy + headline + authored guard. No fix (D19). Cached (D7)."""
    payload = {"candidate_prompt": candidate_prompt, "label": label, "pass_to_fail": sorted(pass_to_fail)}

    def live():
        raw, mcp_calls = asyncio.run(_run_diagnosis(candidate_prompt, label, pass_to_fail))
        data = _parse_json(raw)
        data["mcp_calls"] = mcp_calls
        return data

    return cache.cached("diagnosis", payload, live)
```

- [ ] **Step 4: Write fix_author.py**

Create `agentci/engineer/fix_author.py`:

```python
"""Fix-authoring agent (D19): a separate Gemini agent that, given the root cause, writes ONE
corrective edit to the candidate prompt — kept apart from diagnosis so neither task degrades the
other. Cached (D7)."""
import asyncio
import json
import uuid

from agentci import cache

_FIX_GOAL = """A regression was root-caused in candidate prompt below.

ROOT CAUSE: {root_cause}

CANDIDATE SYSTEM PROMPT:
{candidate_prompt}

Propose ONE corrective edit to the candidate prompt that fixes this root cause while preserving the
candidate's intent (e.g. brevity). Do not over-correct unrelated behaviour.

Return ONLY JSON: {{"revised_prompt":"<full new prompt>","rationale":"<why>"}}"""


def _parse_json(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_fix(candidate_prompt: str, root_cause: dict) -> str:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-fix")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(app_name="agentci-fix", user_id=uid, session_id=sid)
    goal = _FIX_GOAL.format(candidate_prompt=candidate_prompt, root_cause=json.dumps(root_cause))
    final = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=goal)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def author_fix(candidate_prompt: str, root_cause: dict) -> dict:
    """Propose {revised_prompt, rationale} for the root cause (D19). Cached (D7)."""
    payload = {"candidate_prompt": candidate_prompt, "root_cause": root_cause}

    def live():
        return _parse_json(asyncio.run(_run_fix(candidate_prompt, root_cause)))

    return cache.cached("fix", payload, live)
```

- [ ] **Step 5: Delete the old module and its test**

```bash
git rm agentci/engineer/investigate.py tests/test_investigate.py
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_diagnose.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add agentci/engineer/diagnose.py agentci/engineer/fix_author.py tests/test_diagnose.py
git commit -m "feat: split investigate into diagnose() + author_fix() with guard authoring (D19)"
```

---

## Task 8: Persisted-guard store + loader

**Files:**
- Modify: `agentci/engineer/guard.py`
- Modify: `agentci/engineer/mint.py`
- Test: `tests/test_guard.py`, `tests/test_mint.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mint.py`:

```python
def test_build_minted_case_carries_guard():
    from agentci.engineer.mint import build_minted_case
    cluster = {"label": "refund-policy", "policy_id": "R-14"}
    guard = {"kind": "assertion", "slug": "refund-window", "claim": "states window",
             "check": {"type": "must_include", "values": ["14-day"], "mode": "all"}, "origin": {}}
    case = build_minted_case(cluster, "q", "gold", guard=guard)
    import json as _json
    assert _json.loads(case["guard"])["slug"] == "refund-window"
```

Append to `tests/test_guard.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mint.py::test_build_minted_case_carries_guard tests/test_guard.py::test_load_persisted_guards_parses_minted_examples -v`
Expected: FAIL (`build_minted_case` has no `guard` kwarg; `load_persisted_guards` undefined)

- [ ] **Step 3: Add guard to build_minted_case + persist it**

In `agentci/engineer/mint.py`, change `build_minted_case` to accept and store the guard:

```python
def build_minted_case(cluster: dict, question: str, gold: str, index: int = 0, guard: dict | None = None) -> dict:
    """Construct the new eval case row. Always split='tune', source='minted' (D5). Carries the
    authored guard spec (D15) as a JSON string in metadata."""
    label = cluster["label"]
    return {
        "id": f"minted-{label}-{index}",
        "question": question,
        "gold_resolution": gold,
        "policy_id": cluster["policy_id"],
        "split": "tune",
        "source": "minted",
        "kb": _kb_text(),
        "guard": json.dumps(guard or {}),
    }
```

And add `"guard"` to the `metadata_keys` in `persist_minted_case`:

```python
        metadata_keys=["policy_id", "split", "source", "kb", "id", "guard"],
```

- [ ] **Step 4: Add the guard loader**

Append to `agentci/engineer/guard.py`:

```python
import json as _json


def _get_dataset(dataset_name: str):
    from phoenix.client import Client
    return Client().datasets.get_dataset(dataset=dataset_name)


def load_persisted_guards(dataset_name: str) -> list[dict]:
    """Load guard specs from minted examples in the Phoenix dataset (D16). Each minted example
    carries its guard JSON in metadata['guard']."""
    ds = _get_dataset(dataset_name)
    guards = []
    for ex in ds.examples:
        md = ex.get("metadata", {})
        if md.get("source") != "minted":
            continue
        raw = md.get("guard")
        if not raw:
            continue
        guard = _json.loads(raw)
        if guard.get("kind"):
            guards.append(guard)
    return guards
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_mint.py tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agentci/engineer/guard.py agentci/engineer/mint.py tests/test_guard.py tests/test_mint.py
git commit -m "feat: persist guard spec on minted case + dataset guard loader (D15/D16)"
```

---

## Task 9: Report contract additions

**Files:**
- Modify: `agentci/engineer/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_report.py`:

```python
def test_guard_blocked_verdict_and_keys():
    from agentci.engineer.report import assemble_report
    guard_gate = {"tripped": True, "guard": {"slug": "refund-window", "origin": {"label": "refund-policy"}},
                  "ran": 3}
    rep = assemble_report("reg-refund", regression=True, flips={"pass_to_fail": [], "fail_to_pass": []},
                          cluster=None, fix=None, promotion=None, mcp_calls=2,
                          guard_gate=guard_gate)
    assert rep["verdict"] == "guard_blocked"
    assert rep["gate"] == "red"
    assert rep["guard_gate"]["tripped"] is True

def test_proposed_guard_and_review_keys_present_by_default():
    from agentci.engineer.report import assemble_report
    rep = assemble_report("benign", regression=False, flips={"pass_to_fail": [], "fail_to_pass": []},
                          cluster=None, fix=None, promotion=None, mcp_calls=1)
    assert rep["proposed_guard"] is None
    assert rep["guard_review"] is None
    assert rep["guard_gate"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report.py -v`
Expected: FAIL (`assemble_report` has no `guard_gate` kwarg)

- [ ] **Step 3: Extend assemble_report**

Replace the body of `agentci/engineer/report.py` with:

```python
"""Assemble the terminal run report consumed by the CLI and dashboard."""


def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls,
                    investigation=None, proposed_mint=None, guard_gate=None,
                    proposed_guard=None, guard_review=None, meta_metrics=None):
    """Build the run report. Encodes all terminal outcomes incl. guard-block (D16) and no-fix->RED."""
    if guard_gate and guard_gate.get("tripped"):
        verdict, gate = "guard_blocked", "red"          # D16: hard block on a learned guard
    elif not regression:
        verdict, gate = "green_no_regression", "green"
    elif promotion and promotion.get("promotable"):
        verdict, gate = "green_promotable_fix", "green"
    else:
        verdict, gate = "red_no_fix", "red"

    return {
        "candidate_label": candidate_label,
        "regression_detected": regression,
        "flips": flips,
        "cluster": cluster,
        "proposed_fix": fix,
        "promotion": promotion,
        "investigation": investigation,
        "proposed_mint": proposed_mint,
        "guard_gate": guard_gate,          # NEW (D16): persisted guards run + any trip
        "proposed_guard": proposed_guard,  # NEW (D15): authored guard + discrimination evidence
        "guard_review": guard_review,      # NEW (D18): adversarial reviewer verdict
        "meta_metrics": meta_metrics,      # NEW (spec §5.10): surfaced by Plan 07
        "mcp_calls": mcp_calls,
        "verdict": verdict,
        "gate": gate,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/report.py tests/test_report.py
git commit -m "feat: report contract carries guard gate/guard/review/meta keys (D15/D16/D18)"
```

---

## Task 10: Wire the closed loop in run_check

**Files:**
- Modify: `agentci/engineer/__init__.py`
- Test: `tests/test_run_check.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run_check.py`:

```python
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
    # candidate answers omit '14-day' -> guard trips
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
```

Update the existing `test_regressive_candidate_with_good_fix_proposes_promotable` to monkeypatch the new seam: replace the `engineer.investigate` patch with the `engineer.diagnose` + `engineer.author_fix` + `engineer.load_persisted_guards` + `engineer.discrimination_test` + `engineer.attach_independent_correctness` patches shown above, and update `build_minted_case` lambda to accept `guard=None`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_check.py -v`
Expected: FAIL (`engineer` has no `diagnose`/`author_fix`/`load_persisted_guards`/`discrimination_test`/`attach_independent_correctness`)

- [ ] **Step 3: Rewrite run_check**

Replace `agentci/engineer/__init__.py` with:

```python
"""Engineer package: orchestrates one AgentCI check run (closed self-improving loop)."""
from agentci import config
from agentci.engineer.compare import fetch_baseline_via_mcp, compute_flips, is_regression
from agentci.engineer.mint import build_minted_case, persist_minted_case
from agentci.engineer.lift import evaluate_promotion, attach_independent_correctness
from agentci.engineer.report import assemble_report
from agentci.evals.experiment import run_candidate
from agentci.data.dataset import load_tickets
from agentci.engineer.diagnose import diagnose
from agentci.engineer.fix_author import author_fix
from agentci.engineer.guard import run_guard, discrimination_test, load_persisted_guards
from agentci.engineer.review import review_rubric, passes_review

_MCP_CALLS = {"n": 0}


def _mcp_call_count() -> int:
    return _MCP_CALLS["n"]


def _split(rows, split):
    return [r for r in rows if r["split"] == split]


def _ticket_index():
    return {t["id"]: t for t in load_tickets()}


def _gold_for(cluster) -> tuple[str, str]:
    by_id = _ticket_index()
    cid = (cluster.get("case_ids") or [None])[0]
    t = by_id.get(cid, {})
    return (t.get("question", f"Question about {cluster['label']}"),
            t.get("gold_resolution", cluster.get("summary", "")))


def _check_persisted_guards(cand_rows: list[dict]) -> dict | None:
    """Run every persisted guard against the candidate's answers. Return the first trip (D16)."""
    guards = load_persisted_guards(config.DATASET_NAME)
    answer_by_id = {r["id"]: r.get("answer", "") for r in cand_rows}
    for guard in guards:
        for cid in (guard.get("origin", {}).get("case_ids") or list(answer_by_id.keys())):
            if cid not in answer_by_id:
                continue
            if not run_guard(guard, answer_by_id[cid])["passed"]:
                return {"tripped": True, "guard": guard, "case_id": cid, "ran": len(guards)}
    return {"tripped": False, "guard": None, "ran": len(guards)}


def run_check(candidate_prompt: str, label: str) -> dict:
    """Run one AgentCI check: guard gate (D16) -> flip detection -> agentic diagnose (D11) +
    separate fix-author (D19) -> guard discrimination (D15) + review (D18) -> held-out lift on the
    cross-family ruler (D17). Proposes a fix + guard; persists nothing (human-approved, D12)."""
    _MCP_CALLS["n"] = 0
    baseline = fetch_baseline_via_mcp("baseline-tune")
    _MCP_CALLS["n"] += 1
    baseline += fetch_baseline_via_mcp("baseline-heldout")
    _MCP_CALLS["n"] += 1

    cand_tune = run_candidate(candidate_prompt, config.DATASET_NAME, "tune", f"cand-{label}-tune")
    flips = compute_flips(_split(baseline, "tune"), cand_tune)

    # GUARD GATE (D16): a candidate that trips a previously-minted guard is an instant red.
    guard_gate = _check_persisted_guards(cand_tune)
    if guard_gate.get("tripped"):
        return assemble_report(label, True, flips, None, None, None, _mcp_call_count(),
                               guard_gate=guard_gate)

    if not is_regression(_split(baseline, "tune"), cand_tune):
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count(),
                               guard_gate=guard_gate)

    # AGENTIC diagnosis (D11/D15/D19): root cause + taxonomy + headline + authored guard.
    diagnosis = diagnose(candidate_prompt, label, flips["pass_to_fail"])
    _MCP_CALLS["n"] += int(diagnosis.get("mcp_calls", 0))
    cluster = diagnosis["root_cause"]
    guard = diagnosis["guard"]
    headline = diagnosis.get("headline_example", {})

    # Separate fix-author agent (D19).
    fix = author_fix(candidate_prompt, cluster)

    # Guard admission (D15): two-sided discrimination using the headline's wrong vs correct answers.
    disc = discrimination_test(guard, bad_answer=headline.get("candidate_answer", ""),
                               good_answer=headline.get("baseline_answer", ""))
    proposed_guard = {**guard, **disc}

    # Adversarial review for rubric guards (D18).
    guard_review = None
    if guard.get("kind") == "rubric":
        guard_review = review_rubric(guard)

    admitted = disc["admitted"] and (guard_review is None or passes_review(guard_review))

    # Validate the fix on held-out, scored by the independent-family ruler (D17).
    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    by_id = _ticket_index()
    gold_by_id = {cid: by_id.get(cid, {}).get("gold_resolution", "") for cid in [r["id"] for r in fixed_heldout]}
    fixed_heldout = attach_independent_correctness(fixed_heldout, gold_by_id)
    baseline_heldout = attach_independent_correctness(
        _split(baseline, "held_out"),
        {cid: by_id.get(cid, {}).get("gold_resolution", "") for cid in [r["id"] for r in _split(baseline, "held_out")]})
    promotion = evaluate_promotion(baseline_heldout, fixed_heldout)

    # Propose the minted case + guard only if promotable AND the guard earned admission (D12/D15).
    proposed_mint = None
    if promotion["promotable"] and admitted:
        q, gold = _gold_for(cluster)
        proposed_mint = build_minted_case(cluster, q, gold, guard=guard)

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count(),
                           investigation=diagnosis, proposed_mint=proposed_mint,
                           guard_gate=guard_gate, proposed_guard=proposed_guard,
                           guard_review=guard_review)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all — the new run_check tests, plus existing tests still green via the updated monkeypatch seam)

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/__init__.py tests/test_run_check.py
git commit -m "feat: close the loop in run_check — guard gate, diagnose/fix split, cross-family lift (D15-D19)"
```

---

## Task 11: approve_and_mint persists the guard (end-to-end immunity)

**Files:**
- Modify: `agentci/engineer/mint.py` (verify only — `approve_and_mint` already persists `report["proposed_mint"]`, which now carries the guard)
- Test: `tests/test_approve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_approve.py`:

```python
def test_approve_persists_case_with_guard(monkeypatch):
    import agentci.engineer.mint as mint
    captured = {}
    monkeypatch.setattr(mint, "persist_minted_case", lambda case, ds=None: captured.setdefault("case", case))
    report = {"gate": "green", "proposed_mint": {"id": "minted-refund-0", "split": "tune",
              "guard": '{"kind":"assertion","slug":"refund-window"}'}}
    out = mint.approve_and_mint(report)
    assert out["id"] == "minted-refund-0"
    assert "guard" in captured["case"]
```

- [ ] **Step 2: Run test to verify it passes (or fails)**

Run: `uv run pytest tests/test_approve.py::test_approve_persists_case_with_guard -v`
Expected: PASS — `approve_and_mint` is guard-agnostic; the guard rides inside `proposed_mint`. (If `approve_and_mint` gained a gate check that rejects this fixture, adjust the test's `report` to satisfy it.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_approve.py
git commit -m "test: approval persists the minted case with its guard (end-to-end immunity)"
```

---

## Self-Review (completed during authoring)

- **Spec coverage:** §2 integrity spine → Tasks 4 (discrimination), 5 (independent ruler), 6 (review), 10 (wiring). §4 A1/B1 → Tasks 5/6 (independent family), 7 (diagnose/fix split). §5.1 guard spec → Task 7 (authored) + Task 8 (persisted). §5.2 runner → Tasks 2/3. §5.3 discrimination → Task 4. §5.4 review → Task 6. §5.5 cross-family config → Task 1. §5.6 guard gate → Task 10. §5.7 accumulation → Task 8/11. §5.8 taxonomy → Tasks 1/7. §7 report contract → Task 9. §9 decisions → Task 0. **Deferred to Plan 07 (noted):** §5.9 cheap-screener, §5.10 meta-metrics dashboard.
- **Placeholder scan:** none — every code step has complete code; every run step has an exact command + expected result.
- **Type consistency:** guard shape `{kind, slug, claim, check|rubric_prompt, origin}` is identical across Tasks 2/3/4/7/8/10. `run_guard`/`discrimination_test`/`load_persisted_guards`/`diagnose`/`author_fix`/`attach_independent_correctness`/`judge_correctness`/`score_rubric_guard`/`review_rubric`/`passes_review` names match every call site. Report kwargs match Task 9 ↔ Task 10.

## Notes for the executor

- Run `uv run pytest` from the repo root (CWD-relative paths).
- This work should land in an isolated git worktree (`superpowers:using-git-worktrees`) and merge to `main` with `--no-ff`, per repo convention.
- After Plan 06 lands, re-record live fixtures (`record` mode, credentialed) for the new cache namespaces (`diagnosis`, `fix`, `independent_judge`, `guard_judge`, `guard_review`) so the demo replays end-to-end — a credential-gated one-shot, not part of pytest.
