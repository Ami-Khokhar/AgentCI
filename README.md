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
plain English, proposing a fix, and proving it on held-out data. A human approves; the fix is
promoted and a permanent eval case is minted so that exact regression can never silently return.

## How it works

```
candidate.txt ─► agentci check ─► run_check(prompt, label)
   (deterministic CI)  ├─ run candidate over the eval set  →  Phoenix experiment
                       ├─ detect pass→fail flips vs baseline (D10)   ── red / green gate
                       │
   (AGENTIC, D11)      ├─ if red: investigate() — a Gemini reason-act loop that chooses which
                       │          Phoenix MCP queries to run, root-causes the cluster, and
                       │          proposes a fix (tool calls are NOT pre-scripted)
                       │
   (deterministic)     ├─ validate the proposed fix on the HELD-OUT split → lift + gate (D8)
                       └─ assemble report (proposes a minted eval case — does not auto-commit it)
                                │
   surface ──► CLI summary + runs/<label>.json + dashboard
                                └─ human Approve ─► mint permanent guard case (tune partition, D12)
```

- **Target agent** (`agentci/target`) — a config-driven Google ADK support agent (`gemini-2.5-flash`).
  A "candidate" is just a different system prompt.
- **Eval harness** (`agentci/data`, `agentci/evals`) — a 40-ticket SaaS-billing suite with a fixed
  24/16 tune/held-out split, scored by **four LLM-as-judge** dimensions (correctness, groundedness,
  completeness, policy-reference) via Phoenix experiments.
- **Regression Investigator** (`agentci/engineer`) — an ADK `LlmAgent` with `@arizeai/phoenix-mcp`
  mounted as an `McpToolset`; the deterministic CI scaffolding (flip detection, held-out lift,
  promotion gate, confusion matrix) wraps the agentic investigation.
- **Surface** (`agentci/cli.py`, `agentci/server`) — `agentci check` + a single-page dashboard built
  around one demo beat: the fluent-wrong answer beside the correct one, then the agent catching it.

Instrumentation is OpenInference → **Phoenix Cloud** (`phoenix.otel.register(auto_instrument=True)`).

## Quickstart

Requires Python ≥3.13 (managed by [`uv`](https://docs.astral.sh/uv/)) and Node.js (`npx`, for the
Phoenix MCP server).

```bash
uv sync --extra dev          # install
uv run pytest -q             # 61 deterministic tests (no API keys needed)
```

The full suite runs offline: every LLM / judge / MCP / agent call goes through a **record/replay
cache**, so tests and the demo are deterministic.

### Running live (needs credentials)

```bash
cp .env.example .env         # fill in PHOENIX_* and GOOGLE_API_KEY
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

The full frozen-decisions contract (D1–D14) lives in
[`docs/superpowers/plans/2026-06-01-agentci-00-overview.md`](docs/superpowers/plans/2026-06-01-agentci-00-overview.md).
Headlines: pinned models + temperature 0 for determinism (D7); a fix is promotable only on
**held-out** lift ≥ 0.05 with zero held-out regressions (D8); promotion & minting are
**human-approved** (D12); the investigation is a **genuine agentic reason-act loop** over MCP (D11).

A visual walkthrough of the runtime + eval harness is in [`architecture.html`](architecture.html),
and a full action-by-action build journal is in [`agentci-build-log.html`](agentci-build-log.html).

## Status

Plans 01–03 + the agentic-investigator/surface sprint (Plan 05) are implemented and merged, with
**61 passing offline tests**. The credential-gated live steps — generating data, recording the
baseline experiments, and capturing the investigator's real MCP trajectory — are the documented
one-time `record`-mode runs above; everything else is covered deterministically.

## License

[MIT](LICENSE).
