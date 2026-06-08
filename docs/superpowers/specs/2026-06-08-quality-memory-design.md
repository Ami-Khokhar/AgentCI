# AgentCI — Quality Memory design

**Date:** 2026-06-08
**Status:** Approved (brainstorming) — pending implementation plan
**Scope:** Add the self-improving Quality Memory layer to the existing AgentCI codebase, plus reconcile CLI/naming gaps.

## Context

AgentCI is regression CI for AI agents. As of Plan 07 the repo already implements ~90% of the
original product spec: target agent, eval runner with per-case rows, 40-case suite with a 24/16
tune/held-out split, four LLM judges, the regression gate (flips/D10), the **agentic investigator**
(real Phoenix-MCP reason-act loop, D11), held-out lift validation with a promotion gate (D8),
human-gated minting via `POST /api/approve` (D12), agent-authored guards (D15–D18), JSON run
reports, a dashboard, and the `agentci check` CLI.

**The one genuine gap is Quality Memory** — the self-improving institutional-memory layer:

- There is **no persistent, searchable archive** of past failures (failure_type, root_cause,
  successful_fix, failed_fixes, patterns…).
- The investigator is **stateless** — it does not read prior failures before proposing a fix.
- The dashboard has **no Quality Memory timeline**.

The existing guard system persists *executable* regression tests, but it is not a queryable narrative
record and nothing learns patterns *across* failures. Quality Memory is the narrative/learning layer
that sits on top of guards — they are complementary, not competing.

## Goals

1. A persistent, git-tracked Quality Memory store (JSON).
2. The investigator **reads** relevant memory before diagnosing, and the run report/dashboard make
   the influence visible ("Prior knowledge applied: <lesson>").
3. Memory entries are **written only on human approval** — the human-in-the-loop invariant holds.
4. A dashboard **Quality Memory timeline**.
5. Reconcile naming gaps: add the missing `agentci approve` CLI command; document verdict-name
   mapping to the original spec vocabulary.
6. A demo beat that makes self-improvement visible: a second, similar regression whose diagnosis
   cites the lesson learned from the first.

## Non-goals (already built — do not touch)

Target agent, eval runner, judges, lift math, promotion gate, guard system, guard gate, cross-family
improvement ruler. No restructuring of the existing `agentci/` layout. No renaming of existing
verdict strings (they are consumed by the dashboard and tests).

## Design

### New module: `agentci/memory/`

- **`quality_memory.json`** — git-tracked list of entries. Path overridable via the
  `AGENTCI_MEMORY_PATH` env var (mirrors the CWD-relative `runs/` convention) so tests use an
  isolated empty store.
- **`memory.py`** — pure functions, no LLM calls:
  - `load_memory() -> list[dict]`
  - `append_entry(entry: dict) -> None`
  - `find_relevant(flipped_case_ids: list[str]) -> list[dict]` — maps each flipped case to its
    `policy_id`, returns past entries whose affected policies intersect. Policy id is the matching
    key because it is available **before** diagnosis runs (`failure_type`/category only exists
    *after* diagnosis).
  - `format_for_prompt(entries: list[dict]) -> str` — renders matched lessons for injection into the
    diagnose prompt.

**Entry schema** (original-spec fields mapped onto existing report data):

| field | source |
|---|---|
| `failure_type` | `investigation.root_cause.category` (+ `policy_id`) |
| `triggering_prompt_change` | candidate label / short change descriptor |
| `root_cause` | `investigation.root_cause.summary` |
| `lesson` | one-line generalizable pattern (the surfaced string), derived at approval time from `root_cause.summary` + `failure_type` via a deterministic template — no new LLM call |
| `successful_fix` | approved `proposed_fix.rationale` |
| `failed_fixes` | `[]` (populated from `red_no_fix` runs later; empty for now) |
| `affected_cases` | `flips.pass_to_fail` |
| `affected_policies` | policy ids of the flipped cases |
| `evaluator_notes` | which dimensions failed |
| `new_eval_cases` | minted case id + guard slug |
| `approval_status` | `"approved"` |
| `timestamp` | ISO time at approval |

### Read path — investigator reads memory (amends D11)

In `run_check`, **before** `diagnose()`: call `find_relevant(flipped_ids)` and pass the result into
`diagnose(..., prior_lessons=...)`. The agent folds the lessons into its prompt
("Prior lessons from past regressions: …"). This makes the investigator no longer stateless, so it
is recorded as an **explicit amendment to decision D11** in the overview decision table — not a
silent deviation.

**Determinism:** the matched `prior_lessons` become part of the `diagnose` cache payload (an honest
key). Tests run with an empty memory store via `AGENTCI_MEMORY_PATH`. **Known impact:** existing
diagnose replay fixtures must be re-seeded because the payload gains a `prior_lessons` field; the
plan handles this. When `prior_lessons` is empty, the rendered prompt fragment must be a stable
constant so replay keys stay reproducible.

### Write path — only on human approval

`approve_and_mint` (the single path reached by `POST /api/approve`, 409-gated on
`gate=="green"` + a proposed mint) gains one step: after persisting the minted case, build the entry
from the report and call `append_entry(...)` with `approval_status="approved"`. **Reject writes
nothing.** Nothing else writes memory — the human-in-the-loop invariant is preserved.

### Report contract additions (additive only)

Add two keys to the report dict:

- `prior_knowledge` — list of matched memory entries the investigator was given (`[]` when none).
- `memory_entry` — populated post-approval; mirrors the existing `minted` key.

All existing keys are unchanged so the dashboard and tests do not break.

### Dashboard

- New **`GET /api/memory`** endpoint → entries newest-first.
- New **"Quality Memory" timeline panel** (cards: failure_type, lesson, fix, affected cases,
  timestamp).
- In the run view, a **"Prior knowledge applied: <lesson>"** callout shown when `prior_knowledge`
  is non-empty — the visible self-improvement.

### CLI reconcile

- Add **`agentci approve --run runs/<label>.json`** sharing the exact same `approve_and_mint` code
  path as the API (one human-gated path, two surfaces).
- **Verdict naming:** keep the existing verdicts
  (`green_no_regression` / `green_promotable_fix` / `red_no_fix` / `guard_blocked`). Document that
  the original spec's `red_regression_detected` corresponds to `regression_detected: true`. No
  renaming — the dashboard and tests consume the current strings.

### Demo beat (proves self-improvement)

Add a second candidate (`candidates/reg_concise_v2.txt`) that triggers a *similar*
citation-suppression regression. Sequence: approve run #1 → memory gets the "conciseness suppresses
citation" lesson → run #2's investigator cites that prior lesson in its diagnosis, and the dashboard
shows "Prior knowledge applied." The loop is made visible end to end:
regression → diagnosis → fix → validation → approval → memory → stronger future runs.

## Testing

Follow the repo's determinism pattern: `replay` cache mode, `AGENTCI_MEMORY_PATH` pointed at an
isolated/empty store, no network, no asserting on model text.

- `memory.py` pure-function tests: load/append round-trip, `find_relevant` matching by policy id,
  `format_for_prompt` stable output (incl. empty case).
- Read path: `diagnose` is given `prior_lessons`; report carries `prior_knowledge`.
- Write path: approval appends exactly one entry; reject appends none; the only writer is
  `approve_and_mint`.
- Report shape: additive keys present and defaulted.

## Execution method

Worktree-isolated, Sonnet subagents per branch, merged `--no-ff` to `main` (repo convention).
Foundation-first because `report.py` / `run_check` are shared touchpoints:

1. **Branch 1 (foundation):** `agentci/memory/` module + tests. *(blocks the rest)*
2. **Branch 2:** read-path wiring + `diagnose`/report changes.
3. **Branch 3:** write-path in `approve_and_mint` + `agentci approve` CLI.
4. **Branch 4:** dashboard timeline + `/api/memory`.
5. **Branch 5 (last):** demo candidate + docs (D11 amendment, system-diagram, build-log, README).

Branches 2–4 fan out after Branch 1 merges; Branch 5 lands last.
