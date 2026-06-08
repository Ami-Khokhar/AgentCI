# AgentCI — Plan Set Overview (decisions frozen)

> **For agentic workers:** This is the index for a 4-plan set. Execute the plans **in order** (01 → 02 → 03 → 04). Each plan produces working, testable software on its own and uses checkbox (`- [ ]`) steps. REQUIRED SUB-SKILL for each: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`.

**Goal:** Build AgentCI — a regression-CI tool for AI agents that, on a candidate prompt change to an instrumented target agent, detects regressions, root-causes the failure cluster, proposes a fix, mints a permanent eval case, proves held-out lift, and gates promotion behind a human approval.

**Track:** Arize @ Google Cloud Rapid Agent Hackathon. Judged on: technical implementation, meaningful use of tracing + MCP, quality of the self-improvement loop, overall impact.

---

## Frozen decisions (from spec refinement on 2026-06-01)

> **Design revision — 2026-06-01 (post-critique lock-in).** The product is reframed from "an eval pipeline that contains an agent" to **a Gemini Regression Investigator agent** that autonomously investigates its own regressions through Phoenix MCP, the way an SRE would. Newly locked: D11 (agentic investigator), D12 (human-approved promotion & mint), D14 (demo built backward from one beat), and an OSS license (D13, gate-zero). D4/D5/D8 amended below. **Not adopted:** judge-noise confidence intervals (would require abandoning D7 temperature-0 determinism; deferred). These supersede earlier rows where they conflict.

| # | Decision | Value |
|---|----------|-------|
| D1 | **MCP architecture** | Engineer is ADK code that loads `@arizeai/phoenix-mcp` as a native ADK `McpToolset` (in-process MCP **client**), run **locally** for the demo. Cloud Run deploy = stretch goal, not on the critical path. |
| D2 | **Plan structure** | 4 sub-plans, dependency order 01→04. |
| D3 | **Synthetic data** | 40 tickets w/ gold resolutions, single domain (SaaS billing). 60/40 **tune/held-out** split → 24 tune / 16 held-out. Split is fixed and recorded in dataset metadata. |
| D4 | **Candidate battery** | 6 labeled edits: 2 regressive, 2 benign, 2 improving. **The 2 regressive are deliberately different in kind** (Change 4): (a) headline refund-policy **factual omission**, (b) an **over-refusal** regression (routes/declines tickets the KB covers). One investigator characterizing both unlike failures *demonstrates* generalization rather than claiming it. |
| D5 | **Minted eval cases** | Added to the **tune** partition only. NEVER counted toward held-out (would corrupt the held-out lift claim). **Minting is performed on human approval** (D12), not automatically — the run *proposes* the minted case; the engineer commits it. |
| D6 | **Rubric** | All four dimensions (correctness, groundedness, resolution-completeness, policy-reference) are **LLM-as-judge**. No code-check rubric dimension. |
| D7 | **Determinism** | Target agent + judge run at **temperature 0**, pinned model IDs. A **record/replay cache** lets the demo replay a captured real run. Judge stability is verified (GAP-5 mitigation). **Amended 2026-06-05:** engineer + judge re-pinned `gemini-2.5-pro` → `gemini-3.5-flash` — the live key is free-tier, where every pro-class model has zero quota (instant `RESOURCE_EXHAUSTED`); `gemini-3.5-flash` is a generation newer than 2.5-pro and is the newest model the key can run. Target re-pinned `gemini-2.5-flash` → `gemini-2.5-flash-lite` — the free-tier *daily* quota for 2.5-flash was exhausted during the first record attempt; quotas are per-model and the lite tier has higher free limits. Small-target / newer-investigator asymmetry preserved. |
| D8 | **Promotion bar** | A fix **qualifies** iff: held-out mean correctness lift ≥ `+0.05` over baseline **AND** zero held-out cases flip pass→fail. A non-qualifying fix keeps the gate **RED** ("regression confirmed, no qualifying fix"). Qualifying only makes a fix *eligible* — actual promotion is human-approved (D12). |
| D9 | **Pass threshold** | A per-case dimension "passes" iff judge score ≥ `0.7` (scores are 0–1). A case "passes overall" iff all four dimensions pass. |
| D10 | **Regression flag** | A candidate is flagged as a regression iff ≥ 1 tune-partition case flips pass→fail vs. baseline. Benign edits must produce **zero** pass→fail flips → gate stays green. |
| D11 | **Agentic investigator (Change 1)** | The deliverable is a single Gemini-powered **Regression Investigator agent**. When the gate goes red it runs a genuine **reason-act loop**: forms a hypothesis ("refund tickets look worse"), decides which experiments/traces to pull, queries them through Phoenix MCP, checks whether the pattern holds, refines, then writes the root-cause story — tool calls are **not pre-scripted**. The CI scaffolding around it (trigger on prompt change, run the eval set, gate math) stays deterministic and dumb. Demo reproducibility comes from recording the agent's real trajectory and replaying it (D7 cache), not from scripting the loop. |
| D12 | **Human-approved promotion & mint (Change 3)** | The loop **proposes and proves** (generates a candidate fix, validates it on held-out, presents before/after); the **engineer approves**. Promotion and eval-case minting (D5) happen on approval, never auto-merged. Satisfies the hackathon's "under your oversight" theme. |
| D13 | **OSS license (Change 5, gate-zero)** | The public repo carries a detectable OSS license (**MIT**). This is a submission disqualifier, not a score deduction. |
| D14 | **Demo built backward from one beat (Change 6)** | The video lives on one gotcha: the fluent, confident, **wrong** refund answer shown beside the old correct one (the answer a human skimming five outputs would have approved), then the investigator catching exactly that case via Phoenix MCP and naming the cause in plain English. Plan 04's surface is designed to make that 20-second beat land. |
| D15 | **Agent-authored guards** | Guards are agent-authored, hybrid (`assertion`\|`rubric`), and admitted only via a two-sided discrimination test: the guard must FAIL on the regressed answer and PASS on the gold answer. |
| D16 | **Guard gate (behavior C)** | Tripping a persisted guard is an instant RED plus investigator narration of which learned guard tripped and its origin run. Independent of flip detection. |
| D17 | **Frozen cross-family improvement ruler** | Held-out correctness lift (D8) is scored by `IMPROVEMENT_JUDGE_MODEL`, a non-Gemini family distinct from `ENGINEER_MODEL`. The agent cannot grade its own homework. **Amended 2026-06-05:** the ruler transport is env-selected — when `GROQ_API_KEY` is set, the ruler runs `FREE_RULER_MODEL` (Llama on Groq's free tier; still non-Gemini, so the independence constraint holds) instead of paid Anthropic. Same single choke point (`_independent_json`), same cache keys. |
| D18 | **Independent guard review** | Rubric guards are reviewed by `GUARD_REVIEWER_MODEL` (independent family) for specificity, gameability, and over-constraint before admission. |
| D19 | **Diagnose/fix split** | Diagnosis (+ guard authoring) and fix-authoring are separate agents (Engine's lesson: one agent doing both degrades quality). |

> Decisions are the contract. If execution forces a change, STOP and update this table before deviating (per `executing-plans` deviation protocol).
>
> **Build status vs. these decisions:** Plans 01–03 are built/merged and implement D1–D10 (the Engineer loop currently runs as deterministic Python orchestration with single-shot LLM calls). D11 (agentic rewrite of the investigation) and D14 (demo-driven Plan 04) are the **next build sprint**; D12 folds into that rewrite (mint-on-approve), avoiding a throwaway edit to the current auto-mint path. D4's over-refusal regression and D13's license are locked in now.

---

## Where this diverges from the Arize reference repo (intentional)

- **Reference (`Arize-ai/gemini-hackathon`)** runs `@arizeai/phoenix-mcp` **inside Gemini CLI** — a human-driven harness separate from the deployed agent, and creates **no datasets/experiments**.
- **AgentCI** wires Phoenix MCP **into the Engineer agent itself** as an ADK `McpToolset` (D1) and builds a full dataset + experiment harness (Plan 02). This is a deliberate, stronger interpretation of "meaningful use of MCP" — the agent introspects Phoenix at runtime through MCP, not a person.
- Instrumentation is **identical** to the reference: `phoenix.otel.register(auto_instrument=True)` + OpenInference ADK auto-instrumentor → Phoenix Cloud.

---

## Dependency chain & what each plan delivers

```
01 Target agent + tracing      → a traced, config-driven support agent (callable entrypoint)
        │
02 Dataset + eval harness      → Phoenix dataset (40 tix, split), 4 LLM-judge evals, baseline experiment
        │
03 Engineer loop + MCP         → Engineer agent: compare-via-MCP, cluster, fix, mint, lift, gate, battery
        │
04 Surface (dashboard + CLI)   → `agentci check` CLI + dashboard evidencing all 4 judging criteria
```

| Plan | File | Independent test of "done" |
|------|------|----------------------------|
| 01 | `2026-06-01-agentci-01-target-agent-and-tracing.md` | `agentci-target "how do refunds work?"` returns a grounded answer; spans appear in Phoenix. |
| 02 | `2026-06-01-agentci-02-dataset-and-eval-harness.md` | Baseline experiment exists in Phoenix; per-case 0–1 scores for all 4 dims; split tags present. |
| 03 | `2026-06-01-agentci-03-engineer-loop-and-mcp.md` | Battery of 6 → confusion matrix; refund regression caught + fixed + held-out lift proven; one benign passes green; "no-fix" path yields RED. |
| 04 | `2026-06-01-agentci-04-surface-dashboard-and-cli.md` | `agentci check --candidate <file>` prints summary + dashboard URL; dashboard shows trace, MCP call log, confusion matrix, per-case flips, lift, approve/reject. |

---

## Shared tech stack (all plans)

- **Python 3.13**, dependency manager **uv**.
- **Google ADK** (`google-adk`) for both target and Engineer agents; **Gemini** models (`gemini-3.5-flash` for Engineer/judge — see D7 amendment, `gemini-2.5-flash` for target — pinned in `agentci/config.py`).
- **OpenInference** ADK auto-instrumentor + **`arize-phoenix-otel`** (`phoenix.otel.register`).
- **`arize-phoenix-client`** for datasets/experiments.
- **`@arizeai/phoenix-mcp`** via `npx` as an ADK `McpToolset` (requires Node.js/`npx` on PATH).
- **`click`** for the CLI; **FastAPI + Uvicorn** + a single static HTML page for the dashboard.
- **pytest** for tests. LLM-touching code is tested via a **record/replay cache** (D7), never live in CI.

## Repo layout (created across the 4 plans)

```
agentCI/
  pyproject.toml                  # plan 01
  .env.example                    # plan 01
  agentci/
    __init__.py                   # plan 01
    config.py                     # plan 01  (model IDs, temps, thresholds D8/D9)
    tracing.py                    # plan 01  (phoenix.otel.register wrapper)
    cache.py                      # plan 01  (record/replay for determinism, D7)
    target/
      __init__.py                 # plan 01
      agent.py                    # plan 01  (ADK support agent, config-driven prompt)
      kb.py                       # plan 01  (KB lookup tool + KB data accessor)
      run.py                      # plan 01  (callable entrypoint: prompt+ticket -> answer)
    data/
      generate.py                 # plan 02  (Gemini-generate KB + 40 tickets)
      kb.json                     # plan 02  (frozen synthetic KB)
      tickets.json                # plan 02  (frozen 40 tickets w/ gold + split tags)
      dataset.py                  # plan 02  (upload to Phoenix, split metadata)
    evals/
      judges.py                   # plan 02  (4 LLM-judge evaluators, D6)
      experiment.py               # plan 02  (run_experiment wrapper -> per-case scores)
    engineer/
      agent.py                    # plan 03  (ADK Engineer + phoenix McpToolset, D1)
      compare.py                  # plan 03  (fetch baseline per-case via MCP, diff)
      cluster.py                  # plan 03  (LLM failure clustering)
      fix.py                      # plan 03  (draft prompt fix targeting cluster)
      mint.py                     # plan 03  (mint eval case -> tune partition, D5)
      lift.py                     # plan 03  (held-out lift + promotion gate, D8)
      battery.py                  # plan 03  (run 6 candidates -> confusion matrix, D10)
      report.py                   # plan 03  (assemble run report JSON)
    cli.py                        # plan 04  (`agentci` click CLI)
    server/
      app.py                      # plan 04  (FastAPI dashboard + approve/reject)
      static/index.html           # plan 04  (single-page dashboard)
  candidates/                     # plan 03  (the 6 battery candidate prompt files)
  tests/                          # all plans
  docs/superpowers/plans/         # these plans
```

---

## Testing philosophy (read before Plan 01)

LLM outputs are non-deterministic, so **we do not assert on model text in tests**. Instead:

1. **Deterministic scaffolding is unit-tested directly:** config, split logic, pass/fail thresholding (D9), flip detection (D10), lift math (D8), confusion-matrix assembly, report shape, CLI arg parsing, dashboard JSON contract.
2. **LLM-touching code is tested through the record/replay cache (`agentci/cache.py`, Plan 01):** a recorded fixture of a real model/judge response is replayed, so the surrounding logic is tested deterministically while the prompt-assembly and parsing code is exercised with a real payload shape.
3. **Live integration is a manual smoke step**, explicitly called out at the end of each plan (not a pytest test), because it requires Phoenix Cloud + Gemini keys.

This is the GAP-5 determinism mitigation operationalized: the same cache that makes tests deterministic also lets the demo video replay a captured run.
