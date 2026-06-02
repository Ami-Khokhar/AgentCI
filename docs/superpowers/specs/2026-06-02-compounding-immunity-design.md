# Spec: Compounding Regression Immunity (closed self-improving loop)

**Status:** approved design, pre-implementation
**Date:** 2026-06-02
**Builds on:** Plan 05 (agentic investigator + surface), decisions D1–D14

## 1. Goal & success criteria

On a caught regression the investigator **authors a validated, targeted guard**; on human
approval that guard becomes a permanent member of the eval suite; every future candidate is
re-checked against all accumulated guards, so **the same regression can never pass twice**.
"Actually improved" is proven only on a ruler the agent cannot author.

Done when:

1. A regression yields a guard that **provably discriminates** the broken answer from the
   correct one *before* it is ever trusted.
2. A candidate that trips a persisted guard is an **instant red**, and the investigator
   **names which learned guard tripped and where it came from**.
3. "Actually improved" is measured **only by held-out lift on a frozen, cross-family judge**.
4. Demo: replay a candidate the *seed* suite alone would pass, but a previously-minted guard
   catches — compounding immunity, on screen.

## 2. The integrity spine (two principles)

- **Separate the rulers.** Guards measure *recurrence* (the agent authors them). Held-out lift
  on frozen judges measures *improvement* (the agent cannot touch it). A guard may never
  declare progress.
- **Guards earn their place.** No guard is trusted because an LLM wrote it — only because it
  passed a two-sided discrimination test.

Residual risk acknowledged: if the fix-writer and the improvement judge share a model family
they may share a blind spot. Mitigated by **cross-family independence** (§4, D17) — not
eliminated; a small human-authored held-out slice the loop can never mint into is the
ground-truth floor.

## 3. Prior art alignment (LangSmith Engine)

Patterns adopted from Engine's published architecture (validated, not speculative): assertions
over full ground-truth outputs; hybrid code vs LLM-judge evaluators; test the evaluator before
trusting it; constrained failure taxonomy; cheap-screener / expensive-investigator split;
separate issue-diagnosis from fix-authoring. Our daylight vs Engine: **pre-merge CI gate**
(not post-hoc production-trace mining), the **two-sided** discrimination test (Engine checks
the evaluator fires on the bad trace; we also require it pass the known-good answer), the
**frozen cross-family improvement ruler** (anti self-grading), and **Phoenix/Arize-native**
(Engine is locked to LangSmith traces).

## 4. Resolved decisions

- **Decision A → A1:** cross-family independence. Investigator / fix-author run on the Gemini
  model (`ENGINEER_MODEL`); the **frozen held-out improvement judge** and the **guard
  reviewer** run on a **non-Gemini family** (`IMPROVEMENT_JUDGE_MODEL`, `GUARD_REVIEWER_MODEL`).
  The ruler and the optimizer do not share a brain.
- **Decision B → B1:** split diagnosis from fix-authoring. The investigator diagnoses
  (root cause + headline example) and authors the guard; a **separate fix-author agent** writes
  the proposed prompt fix.

## 5. Components (new / modified)

### 5.1 Guard spec (data model) — new
Emitted by the investigator as structured output alongside the diagnosis:

```
guard = {
  kind: "assertion" | "rubric",
  slug: "refund-window-stated",
  claim: "A correct answer states the refund window length and its eligibility conditions",
  check:  {...},          # kind=assertion: deterministic (must_include / must_cite policy_id / regex)
  rubric_prompt: "...",   # kind=rubric: scoped LLM-judge prompt
  origin: { label, policy_id, category, case_ids, minted_in_run }
}
```

Hybrid (Flavor 4): assertion when the property is crisp, scoped rubric when semantic — often
both for one regression (assertion = hard floor, rubric = semantic backstop).

### 5.2 Guard runner (`engineer/guard.py`) — new
Executes a guard against an answer → `{passed, detail}`. Assertion path is pure deterministic
code. Rubric path is an LLM-judge call through `cache.cached("guard_judge", …)` scored on the
**independent family** (`IMPROVEMENT_JUDGE_MODEL`), so guard scoring never runs on the same
brain that authored the candidate fix. Result folds into the existing per-case
`passed`/`scores` contract.

### 5.3 Guard discrimination test (admission gate) — new, the integrity core
Before a guard may be proposed, run it against:
- the **regressed answer** → **must FAIL** (it detects the bug), and
- the **baseline/gold answer** → **must PASS** (it does not reject good answers).

Fail either → reject; the investigator refines (capped retries, default 2). Only two-sided
survivors become `proposed_mint`. The pass/fail evidence is recorded for the report and demo.

### 5.4 Adversarial rubric review — new
For `kind=rubric`, an **independent-family** reviewer (`GUARD_REVIEWER_MODEL`) scores the rubric
on specificity / gameability / over-constraint. Below threshold → reject or flag. (Assertions
are largely covered by the discrimination test; review is optional for them.)

### 5.5 Cross-family judge config — modified
`config.py` adds `IMPROVEMENT_JUDGE_MODEL` and `GUARD_REVIEWER_MODEL`, both a non-Gemini family,
distinct from `ENGINEER_MODEL`. The held-out **correctness** judge used by the promotion gate
(D8) switches to `IMPROVEMENT_JUDGE_MODEL`. All such calls remain wrapped in `cache.cached` and
replay-seeded; the provider call is a thin addition behind the cache boundary.

### 5.6 Guard gate in `run_check` — modified (gate behavior C)
New early step: run all *persisted* guards against the candidate's answers. Any trip → gate
**red**, `verdict="guard_blocked"`, and the investigator narrates *"guard `minted-refund-0`,
minted in run #2, tripped — the refund-window omission is back."* Hard block, independent of
flip detection.

### 5.7 Accumulation — modified
`approve_and_mint` persists the **guard spec alongside the case**; future runs load and
re-check all guards. Suite grows monotonically. Minted cases remain tune-only (D5).

### 5.8 Constrained failure taxonomy — new
Root cause must classify into a fixed set: `factual_omission`, `over_refusal`, `policy_miscite`,
`hallucination`, `format_regression`. Controls quality and keeps guards consistent.

### 5.9 Cheap-screener / expensive-investigator split — new
A cheap model (`gemini-2.5-flash`) triages flips to the headline cluster; the expensive
investigator digs. For our 40-case suite this is a credible-agentic-design signal more than a
scale necessity.

### 5.10 Transparency meta-metrics — new (dashboard)
Surface **guard admission rate**, **guard count over runs (immunity curve)**, **held-out
correctness trend (frozen ruler)**, and **which guard tripped**. Integrity made visible.

## 6. Data flow (the closed loop)

```
candidate → run_check
  ├─ [GUARD GATE] run persisted guards vs candidate answers
  │     └─ any trip? → RED + investigator narrates which guard (C) → report(verdict=guard_blocked)
  ├─ run candidate over tune; compute flips vs baseline
  ├─ no regression → green
  └─ regression:
       ├─ cheap screener → headline cluster
       ├─ investigator (diagnose): root_cause (taxonomy) + headline_example + guard spec
       ├─ fix-author (separate agent): proposed_fix
       ├─ GUARD DISCRIMINATION TEST  (fail-on-bad, pass-on-gold) → refine/reject
       ├─ adversarial rubric review (independent family)
       ├─ validate fix on held-out via CROSS-FAMILY frozen judge → lift gate (D8)
       └─ promotable & guard admitted → proposed_mint = {fix, guard}
  → assemble report (+ meta-metrics)
→ human approve → persist fix + guard → guard joins permanent suite
```

## 7. Report dict additions (the CLI/dashboard contract)

New keys (additive — existing consumers keep working): `guard_gate` (which persisted guards ran
and any trip), `proposed_guard` (the authored guard + discrimination evidence), `guard_review`
(adversarial reviewer verdict), `meta_metrics`. `verdict` gains `guard_blocked`. `proposed_mint`
now carries the guard spec.

## 8. Determinism & testing

Assertion guards are deterministic. Rubric scoring, the adversarial reviewer, and the
cross-family held-out judge all wrap `cache.cached` and are replay-seeded; tests never hit the
network and never assert on model text. New tests: discrimination test (both sides), guard gate
trip → red, cross-family judge cache keying, meta-metric math, taxonomy validation.

## 9. Decision-table additions (append to `…-00-overview.md` as step 0 of implementation)

- **D15 — Agent-authored guards.** Guards are agent-authored, hybrid (`assertion`|`rubric`),
  admitted only via the two-sided discrimination test (fails on the regressed answer, passes on
  the gold answer).
- **D16 — Guard gate (behavior C).** Tripping a persisted guard is an instant red plus
  investigator narration of which learned guard tripped and its origin run.
- **D17 — Frozen cross-family improvement ruler.** Improvement is measured only by held-out
  lift on a frozen judge whose model family differs from the investigator/fix-author
  (`IMPROVEMENT_JUDGE_MODEL` ≠ `ENGINEER_MODEL`). The agent cannot grade its own homework.
- **D18 — Independent guard review.** Rubric guards are reviewed by an independent-family model
  (`GUARD_REVIEWER_MODEL`) for specificity, gameability, and over-constraint.
- **D19 — Diagnose/fix split.** Diagnosis (+ guard authoring) and fix-authoring are separate
  agents (Engine's lesson: one agent doing both degrades quality).

## 10. Out of scope (YAGNI)

Production-trace mining (we are pre-merge by design); trajectory compression (our suite is
small); any auto-promote / auto-mint (human approval stays structural, D12).
