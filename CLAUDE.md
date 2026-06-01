# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AgentCI is **regression CI for AI agents**. On a candidate prompt change to an instrumented target
agent, it detects regressions, and when the gate goes red a Gemini "Regression Investigator" agent
autonomously root-causes the failure through the Phoenix MCP server, proposes a fix, proves held-out
lift, and gates promotion behind a human approval. Built for the Arize × Google Cloud hackathon.

## Commands

Toolchain is **`uv`** (manages its own Python; the `>=3.13` pin currently resolves to 3.14). Node.js
/ `npx` must be on PATH (the engineer agent launches `@arizeai/phoenix-mcp` via stdio).

```bash
uv sync --extra dev                              # install (incl. pytest, pytest-asyncio)
uv run pytest -q                                 # full suite — runs fully offline, no API keys
uv run pytest tests/test_lift.py -v              # one file
uv run pytest tests/test_lift.py::test_mean_correctness -v   # one test
uv run agentci check --candidate candidates/reg_refund.txt   # CLI entrypoint
uv run uvicorn agentci.server.app:app --reload   # dashboard at http://127.0.0.1:8000/?run=<label>
```

There is no build step and no linter configured. Run pytest from the **repo root** — several paths
are CWD-relative (`battery.py` reads `candidates/`, the CLI/server read/write `runs/`).

## The determinism constraint (read this before touching any LLM-touching code)

Everything is built around making non-deterministic LLM behavior testable and the demo replayable.
This shapes the whole codebase:

- **Models run at temperature 0, pinned IDs** (`agentci/config.py`). The target *and* the engineer
  agent both pass `generate_content_config=types.GenerateContentConfig(temperature=config.TEMPERATURE)`
  — if you add an agent, pin it too.
- **Every LLM / judge / MCP / agent call is wrapped in `agentci/cache.py`** via
  `cache.cached(namespace, payload, live_fn)`. Mode is `AGENTCI_CACHE_MODE` (`replay` default /
  `record` / `live`). Tests set `replay` and pre-seed a fixture keyed by `cache._key(namespace, payload)`,
  so `live_fn` (the real model call) never fires. **Tests never assert on model text** and never hit
  the network.
- Consequence: when you add an LLM-backed function, follow the pattern — pure prompt-assembly +
  `cache.cached(...)` + a replay-seeded test. The cache payload **is** the cache key, so include
  everything that changes the output in it (e.g. judges include `policy_id` because the prompt uses it).
- "Live" steps (data generation, Phoenix dataset upload, baseline experiments, recording the
  investigator's real MCP trajectory) are **credential-gated manual one-shots in `record` mode**, never
  part of pytest. They need `.env` (`PHOENIX_*`, `GOOGLE_API_KEY`); see README "Running live".

## Architecture (the layers, and how data flows)

Four layers under `agentci/`, in dependency order:

1. **target/** — a config-driven Google ADK support agent (`gemini-2.5-flash`). A "candidate" is just a
   different system-prompt string passed to `build_support_agent(prompt)`. `run.answer_ticket(prompt,
   ticket) -> {"answer": str}` is the cached entrypoint.
2. **data/ + evals/** — the eval harness. `data/dataset.py` loads the frozen 40-ticket suite with a
   fixed 24/16 tune/held-out split and uploads it to Phoenix. `evals/judges.py` has the four
   LLM-as-judge evaluators; `evals/experiment.py::run_candidate(prompt, dataset, split, name)` runs the
   target over a split as a Phoenix experiment and returns **per-case rows** — the central contract:
   `{"id","split","passed","scores":{dim:float},"answer"}`.
3. **engineer/** — detection + the agentic investigator. Deterministic CI math (`compare.py` flips/D10,
   `lift.py` held-out lift + promotion gate/D8) wraps the **agentic** part: `investigate.py` drives the
   `LlmAgent` (`agent.py`, which mounts `@arizeai/phoenix-mcp` as an `McpToolset`) with an *open goal* —
   the agent chooses its own MCP queries (a real reason-act loop, not a script) and returns a structured
   root-cause + proposed fix + the real `mcp_calls` count. `__init__.run_check(prompt, label)` is the
   orchestration spine; `report.py::assemble_report` produces the terminal report dict.
4. **cli.py + server/** — the surface. `agentci check` writes `runs/<label>.json`; `server/app.py` is a
   FastAPI app serving those reports and the approve action, with `server/static/index.html` as the
   single-page dashboard.

**The report dict is the contract** between `run_check` and the CLI/dashboard. Keys: `candidate_label,
regression_detected, flips, cluster, proposed_fix, promotion, investigation, proposed_mint, mcp_calls,
verdict, gate`. `verdict ∈ {green_no_regression, green_promotable_fix, red_no_fix}`. Don't change its
shape without updating both consumers.

**Human-in-the-loop is enforced structurally:** `run_check` *proposes* a minted eval case
(`proposed_mint`) but never persists it. The only path that calls `persist_minted_case` is
`engineer.mint.approve_and_mint`, reached only via the dashboard's `POST /api/approve` (409-gated on
`gate=="green"` + a proposed mint). Keep it that way — nothing should auto-mint or auto-promote.

## Frozen decisions are the contract

`docs/superpowers/plans/2026-06-01-agentci-00-overview.md` holds decisions **D1–D14** (models,
thresholds, split, the agentic-investigator reframe, human-approved promotion, the demo beat). These
are binding. **If implementation forces a change to a decision, STOP and update that table first** —
don't silently deviate. The per-plan specs live alongside it (`...-01`..`-05`); Plan 05 supersedes the
old Plan 04, and `engineer/cluster.py`/`fix.py` are superseded by `investigate.py` (kept but unused by
`run_check`).

## Conventions in this repo

- Work was done plan-by-plan in isolated git worktrees, each merged to `main` with `--no-ff`. The
  decision table is updated before deviating; review nits and plan-bugs are fixed in separate commits.
- `agentci-build-log.html` is a running action+reasoning journal and `architecture.html` is a visual
  overview — both are committed docs, not generated; update the build log when you do substantive work.
- `runs/`, `promoted/`, `.agentci_cache/`, and `.worktrees/` are git-ignored.
