# AgentCI — Regression CI for AI agents

> A Gemini **Regression Investigator agent** that investigates its own regressions through its
> observability stack, the way an SRE would — and remembers them forever.

Built for the **Arize × Google Cloud Rapid Agent Hackathon**.

---

## The problem

Everyone is shipping AI agents. Almost no one can answer: *"I changed my agent's prompt — did I
make it better, or silently break something?"* For traditional code we solved this with regression
CI: change code → tests run → a red build blocks the merge. For agents that safety net doesn't
exist. A one-line prompt edit to "be more concise" can quietly drop a refund-eligibility rule; the
agent still returns a fluent, confident answer — it's just *wrong*, and a human skimming five
outputs would approve it.

**AgentCI is regression CI for that.** On a candidate prompt change it detects regressions, and when
the gate goes red a Gemini agent **autonomously investigates why** — forming a hypothesis, querying
the relevant experiments and traces through the **Phoenix MCP server**, naming the root cause in
plain English, and **authoring a targeted guard** (a deterministic assertion and/or scoped
LLM-judge rubric) that catches that exact failure. A separate agent proposes the prompt fix; the fix
must prove held-out lift on a **frozen cross-family ruler**. A human approves; the fix is promoted
and the guard joins the permanent suite — so that exact regression can **never silently return**.
This is the compounding part: every regression caught makes the suite permanently stronger.

## How it works

```
candidate.txt ─► agentci check ─► run_check(prompt, label)
   (deterministic CI)  ├─ GUARD GATE (D16): run every previously-minted guard; a trip = instant RED
                       ├─ run candidate over the eval set  →  Phoenix experiment
                       ├─ detect pass→fail flips vs baseline (D10)   ── red / green gate
                       │
   (AGENTIC, D11/D19)  ├─ if red: diagnose() — a Gemini reason-act loop that chooses which Phoenix
                       │          MCP queries to run, root-causes the cluster, classifies the failure
                       │          taxonomy, and AUTHORS a guard (tool calls are NOT pre-scripted)
                       ├─          author_fix() — a SEPARATE agent writes the proposed prompt fix
                       │
   (deterministic)     ├─ admit the guard via a two-sided discrimination test (D15: must FAIL the
                       │          regressed answer, PASS the gold) + adversarial review for rubrics (D18)
                       ├─ validate the fix on the HELD-OUT split, scored by the cross-family ruler →
                       │          lift + promotion gate (D8/D17)
                       └─ assemble report (proposes a minted case + guard — does not auto-commit them)
                                │
   surface ──► CLI summary + runs/<label>.json + dashboard
                                └─ human Approve ─► mint permanent case + guard (tune partition, D12)
```

- **Target agent** (`agentci/target`) — a config-driven Google ADK support agent (`gemini-2.5-flash`).
  A "candidate" is just a different system prompt.
- **Eval harness** (`agentci/data`, `agentci/evals`) — a 40-ticket SaaS-billing suite with a fixed
  24/16 tune/held-out split, scored by **four LLM-as-judge** dimensions (correctness, groundedness,
  completeness, policy-reference) via Phoenix experiments.
- **Regression Investigator** (`agentci/engineer`) — an ADK `LlmAgent` with `@arizeai/phoenix-mcp`
  mounted as an `McpToolset`, split into a **diagnose** agent (root cause + guard authoring) and a
  separate **fix-author** agent (D19). The deterministic CI scaffolding (flip detection, the guard
  gate, guard discrimination/review, held-out lift, promotion gate, confusion matrix) wraps the
  agentic steps. The held-out improvement ruler and the guard reviewer run on a **non-Gemini family**
  (`claude-haiku-4-5`) so the agent can't grade its own homework (D17/D18).
- **Surface** (`agentci/cli.py`, `agentci/server`) — `agentci check` + a single-page dashboard built
  around one demo beat: the fluent-wrong answer beside the correct one, the agent catching it, and
  the learned guard that blocks it forever after.

Instrumentation is OpenInference → **Phoenix Cloud** (`phoenix.otel.register(auto_instrument=True)`).

The run report's `verdict` is one of `green_no_regression`, `green_promotable_fix`, `red_no_fix`, or
`guard_blocked` (a candidate tripping a previously-learned guard — caught instantly, no investigation
needed).

## Quickstart

Requires Python ≥3.13 (managed by [`uv`](https://docs.astral.sh/uv/)) and Node.js (`npx`, for the
Phoenix MCP server).

```bash
uv sync --extra dev          # install
uv run pytest -q             # 82 deterministic tests (no API keys needed)
```

The full suite runs offline: every LLM / judge / MCP / agent call goes through a **record/replay
cache**, so tests and the demo are deterministic.

### Running live (needs credentials)

```bash
cp .env.example .env         # fill in PHOENIX_*, GOOGLE_API_KEY, and ANTHROPIC_API_KEY
# 1. build the dataset + baseline experiments (one-shot, recorded)
uv run python -m agentci.data.generate
uv run python -c "from agentci.tracing import init_tracing; from agentci.evals.experiment import run_candidate; from agentci import config; import os; os.environ['AGENTCI_CACHE_MODE']='record'; init_tracing(); run_candidate(config.BASELINE_SUPPORT_PROMPT, config.DATASET_NAME, 'tune', 'baseline-tune'); run_candidate(config.BASELINE_SUPPORT_PROMPT, config.DATASET_NAME, 'held_out', 'baseline-heldout')"
# 2. run a check on a candidate prompt
uv run agentci check --candidate candidates/reg_refund.txt
# 3. open the dashboard
uv run uvicorn agentci.server.app:app --reload   # http://127.0.0.1:8000/?run=reg_refund
```

## Candidate battery (D4)

Six labelled prompt edits in `candidates/` prove detection generalizes and doesn't cry wolf:
**2 regressive** (`reg_refund` factual omission, `reg_overrefusal` over-routing — deliberately
different *kinds*), **2 benign** (reword, reformat), **2 improving** (citation format, completeness
checklist). The battery scores into a confusion matrix; the target is `tp=2, fp=0` (no benign or
improving edit is ever flagged).

## Design decisions

The full frozen-decisions contract (D1–D19) lives in
[`docs/superpowers/plans/2026-06-01-agentci-00-overview.md`](docs/superpowers/plans/2026-06-01-agentci-00-overview.md).
Headlines: pinned models + temperature 0 for determinism (D7); a fix is promotable only when it is
**no worse than baseline on held-out** (lift ≥ 0) with zero held-out regressions (D8, recovery-correct
gate); promotion & minting are **human-approved** (D12); the investigation is a **genuine agentic
reason-act loop** over MCP (D11).
The compounding-immunity decisions: guards are **agent-authored** and admitted only via a two-sided
discrimination test (D15); tripping a persisted guard is an **instant red** (D16); the held-out
improvement ruler and the rubric reviewer run on an **independent model family** so the agent can't
grade its own work (D17/D18); diagnosis and fix-authoring are **separate agents** (D19).

A visual walkthrough of the runtime + eval harness (Mermaid flow traced from `run_check()`) is in
[`docs/system-diagram.md`](docs/system-diagram.md).

## Quality Memory

AgentCI gets smarter with every approved regression. When a human approves a run, the fix and the
lesson are archived in a git-tracked store (`agentci/memory/quality_memory.json`). The next time the
investigator encounters a similar failure — matched by the flipped cases' `policy_id` — it is handed
the prior lesson before diagnosing, so it starts with context rather than from scratch.

**The rule:** the investigator READS relevant entries (matched by `policy_id`) before diagnosing;
entries are WRITTEN only on human approval. Reject writes nothing. This is a structural invariant:
`record_approval` is the single write path, reachable only via `POST /api/approve` and the
`agentci approve` CLI.

**New surfaces:**
- `agentci approve --run runs/<label>.json` — CLI approval path (alternative to the dashboard button).
- `GET /api/memory` — returns the full Quality Memory timeline as JSON.
- Dashboard "Quality Memory" timeline panel and a **"Prior knowledge applied."** callout when
  `prior_knowledge` is non-empty in the run report.

**Determinism / testing:** tests point `AGENTCI_MEMORY_PATH` at a `tmp_path` fixture so the real
store is never read or written during the suite. Matched lessons join the diagnose cache key only when
non-empty, keeping all existing replay fixtures valid.

This is locked as decision D20; the D11 amendment (investigator is no longer stateless) is recorded
in [`docs/superpowers/plans/2026-06-01-agentci-00-overview.md`](docs/superpowers/plans/2026-06-01-agentci-00-overview.md).

## Status

Plans 01–03, the agentic-investigator/surface sprint (Plan 05), the compounding-immunity engine
(Plan 06, D15–D19) and its dashboard surfacing (Plan 07) are implemented and merged, with
**82 passing offline tests**. The credential-gated live steps — generating data, recording the
baseline experiments, and capturing the investigator's real MCP trajectory — are the documented
one-time `record`-mode runs above; everything else is covered deterministically.

## License

[MIT](LICENSE).
