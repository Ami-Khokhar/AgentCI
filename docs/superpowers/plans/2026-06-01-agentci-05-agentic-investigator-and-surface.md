# AgentCI Plan 05 — Agentic Investigator + Surface (supersedes Plan 04, revises Plan 03)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`. Steps use checkbox (`- [ ]`). **Depends on Plans 01–03.** This plan implements the post-critique lock-in: **D11** (agentic Regression Investigator), **D12** (human-approved promotion & mint), and **D14** (surface built backward from the demo beat). It revises Plan 03's `run_check` and replaces Plan 04.

**Goal:** Turn AgentCI from "an eval pipeline that contains an agent" into **a Gemini Regression Investigator agent** that, when the gate goes red, runs a genuine reason-act loop over Phoenix MCP to root-cause the failure and propose a fix — then surface that through a CLI and a single-page dashboard whose whole job is to land one demo beat: the fluent, confident, *wrong* refund answer beside the correct one, caught by the agent.

**What stays deterministic (CI scaffolding, D11):** trigger on a candidate prompt, run the eval set, detect pass→fail flips (D10), compute held-out lift + the promotion gate (D8). These are dumb and reproducible.

**What becomes agentic (D11):** the *investigation* — forming a hypothesis, deciding which experiments/traces to pull through Phoenix MCP, checking whether the pattern holds, refining, and writing the root-cause story + proposed fix. Tool calls are **not pre-scripted**. Determinism for tests/demo comes from recording the agent's real trajectory (incl. its MCP-call count) and replaying it through the Plan-01 cache — not from scripting the loop.

**Human-in-the-loop (D12):** the run *proposes and proves* (validates the proposed fix on held-out); minting the permanent eval case + promotion happen on **approval** via the dashboard, never automatically.

**Tech stack:** google-adk (`LlmAgent`, `McpToolset`), `@arizeai/phoenix-mcp`, google-genai, click, FastAPI + uvicorn, pytest (+ Plans 01–03 stack).

---

## Architecture & contracts

```
candidate.txt ─► agentci check ─► run_check(prompt, label)
                                     │  (deterministic CI)
                                     ├─ fetch_baseline_via_mcp(tune|heldout)   [MCP read, cached]
                                     ├─ run_candidate(prompt, tune)            [Phoenix experiment]
                                     ├─ compute_flips / is_regression (D10)
                                     │
                                     ├─ if regression ──► investigate(prompt, label, pass_to_fail)
                                     │        (AGENTIC reason-act loop over Phoenix MCP, cached)
                                     │        → {hypothesis, investigation_steps[], root_cause,
                                     │           proposed_fix, mcp_calls}
                                     │
                                     ├─ run_candidate(proposed_fix, heldout)   [deterministic]
                                     ├─ evaluate_promotion (D8)                [deterministic gate]
                                     └─ assemble_report(... investigation, proposed_mint)  [no auto-mint, D12]
                                          │
                       runs/<label>.json ◄┘
                                          │
              dashboard (FastAPI + static)│  GET /api/report/<label>, POST /api/approve/<label>
                                          └─ approve ─► approve_and_mint(report) ─► persist_minted_case (D5/D12)
```

**Report contract (extends Plan 03; Plan 04 surface renders this):**
```jsonc
{
  "candidate_label": str,
  "regression_detected": bool,
  "flips": {"pass_to_fail": [id...], "fail_to_pass": [id...]},
  "cluster": {"label","policy_id","summary","case_ids"} | null,   // == investigation.root_cause
  "proposed_fix": {"revised_prompt","rationale"} | null,
  "promotion": {"lift","n","heldout_regressions","promotable","reason"} | null,
  "investigation": {"hypothesis","investigation_steps":[...],"root_cause":{...},"proposed_fix":{...},"mcp_calls":int} | null,  // NEW
  "proposed_mint": {minted-case row} | null,                      // NEW (D12: built, not persisted)
  "mcp_calls": int,
  "verdict": "green_no_regression" | "green_promotable_fix" | "red_no_fix",
  "gate": "green" | "red"
}
```

**`cluster.py` / `fix.py`** (Plan 03) are **subsumed** by `investigate()` in the orchestrator — the agent now produces root cause + fix in one reason-act loop. The modules remain as tested library functions (non-agentic fallback) but `run_check` no longer calls them.

---

### Task 1: Agentic investigator (D11)

**Files:** Create `agentci/engineer/investigate.py`; Test `tests/test_investigate.py`.

`investigate(candidate_prompt, label, pass_to_fail)` drives the Engineer `LlmAgent` (Plan 03 `build_engineer_agent`, which already mounts Phoenix MCP) with an open-ended investigation **goal** — the agent decides which MCP queries to run. It returns the structured investigation dict and the real MCP tool-call count, all wrapped in the cache (record/replay, D7) so the demo replays deterministically and `mcp_calls` reflects the recorded trajectory (closes the Plan-03 C1 defect honestly).

- [ ] **Step 1: failing test** (replay; never drives a live agent):
```python
# tests/test_investigate.py
import json
from agentci import cache
from agentci.engineer import investigate as inv

def test_investigate_replays_structured_result(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    result = {"hypothesis": "refund answers omit the window",
              "investigation_steps": ["pulled cand-reg-refund-tune via MCP", "compared to baseline-tune"],
              "root_cause": {"label": "refund-policy", "policy_id": "refund-policy",
                             "summary": "drops the 14-day window", "case_ids": ["t00"]},
              "proposed_fix": {"revised_prompt": "P + state refund window", "rationale": "restores detail"},
              "mcp_calls": 3}
    (tmp_path / (cache._key("investigation", payload) + ".json")).write_text(json.dumps(result))
    out = inv.investigate("P", "reg-refund", ["t00"])
    assert out["root_cause"]["label"] == "refund-policy"
    assert out["mcp_calls"] == 3

def test_parse_investigation_strips_fence():
    raw = "```json\n{\"hypothesis\":\"h\",\"investigation_steps\":[],\"root_cause\":{},\"proposed_fix\":{}}\n```"
    out = inv._parse_investigation(raw)
    assert out["hypothesis"] == "h"
```

- [ ] **Step 2:** run → `ModuleNotFoundError`.
- [ ] **Step 3: write `agentci/engineer/investigate.py`:**
```python
"""Agentic regression investigator (D11): a Gemini reason-act loop over Phoenix MCP.

When the gate is red, this drives the Engineer LlmAgent (which mounts the Phoenix MCP
toolset) with an open-ended GOAL, not a script. The agent decides which experiments/traces
to query through MCP, forms and checks a hypothesis, and returns a structured root-cause +
proposed fix. The whole run (including the real MCP tool-call count) is cached (D7), so the
demo replays the captured trajectory deterministically.
"""
import asyncio
import json
import uuid

from agentci import cache

_INVESTIGATION_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped from PASS to FAIL versus the baseline: {pass_to_fail}.

Investigate WHY, like a reliability engineer. Use your Phoenix MCP tools to pull the
candidate experiment ('cand-{label}-tune'), the baseline experiment ('baseline-tune'),
and the per-case annotations/traces for the flipped cases. Form a hypothesis about the
common failure pattern, verify it holds across the flipped cases (and is absent from
still-passing cases), and refine if needed. Then propose ONE corrective edit to the
candidate system prompt that fixes the cluster while preserving the candidate's intent
(e.g. brevity). Do not over-correct unrelated behaviour.

CANDIDATE SYSTEM PROMPT:
{candidate_prompt}

Return ONLY JSON:
{{"hypothesis": "<initial hypothesis>",
  "investigation_steps": ["<each MCP query / check you ran, in order>"],
  "root_cause": {{"label":"<short>","policy_id":"<kb id>","summary":"<one sentence>","case_ids":["..."]}},
  "proposed_fix": {{"revised_prompt":"<full new prompt>","rationale":"<why>"}}}}"""


def _parse_investigation(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_investigation(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> tuple[str, int]:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-investigator")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-investigator", user_id=uid, session_id=sid
    )
    goal = _INVESTIGATION_GOAL.format(
        label=label, pass_to_fail=pass_to_fail, candidate_prompt=candidate_prompt
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


def investigate(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> dict:
    """Agentic root-cause + proposed fix via a Phoenix-MCP reason-act loop (D11). Cached (D7).

    Returns {"hypothesis","investigation_steps","root_cause","proposed_fix","mcp_calls"}.
    """
    payload = {"candidate_prompt": candidate_prompt, "label": label, "pass_to_fail": sorted(pass_to_fail)}

    def live():
        raw, mcp_calls = asyncio.run(_run_investigation(candidate_prompt, label, pass_to_fail))
        data = _parse_investigation(raw)
        data["mcp_calls"] = mcp_calls  # captured from the real trajectory; replayed deterministically
        return data

    return cache.cached("investigation", payload, live)
```
- [ ] **Step 4:** run → 2 passed.
- [ ] **Step 5:** commit `feat: agentic regression investigator over Phoenix MCP (D11)`.

---

### Task 2: Rewrite `run_check` to use the investigator (D11) + report fields

**Files:** Modify `agentci/engineer/report.py` (add `investigation`, `proposed_mint`); Modify `agentci/engineer/__init__.py` (`run_check`); update `tests/test_report.py`, `tests/test_run_check.py`.

`report.py` — add two optional params (backward-compatible), include in the dict:
```python
def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls,
                    investigation=None, proposed_mint=None):
    ...  # verdict/gate logic unchanged
    return {..., "investigation": investigation, "proposed_mint": proposed_mint, ...}
```
`run_check` — replace the scripted cluster/fix calls with the agentic `investigate()`, and STOP auto-minting (D12): build the proposed mint into the report instead. Deterministic detect + validate stay.
```python
from agentci.engineer.investigate import investigate
...
    if not is_regression(_split(baseline, "tune"), cand_tune):
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count())

    investigation = investigate(candidate_prompt, label, flips["pass_to_fail"])
    _MCP_CALLS["n"] += int(investigation.get("mcp_calls", 0))
    cluster = investigation["root_cause"]
    fix = investigation["proposed_fix"]

    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    promotion = evaluate_promotion(_split(baseline, "held_out"), fixed_heldout)

    proposed_mint = None
    if promotion["promotable"]:
        q, gold = _gold_for(cluster)
        proposed_mint = build_minted_case(cluster, q, gold)  # D12: built, NOT persisted here

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count(),
                           investigation=investigation, proposed_mint=proposed_mint)
```
Tests: `test_report.py` gains assertions that `investigation`/`proposed_mint` round-trip; `test_run_check.py` monkeypatches `engineer.investigate` (instead of cluster_failures/draft_fix) and asserts `report["verdict"]=="green_promotable_fix"`, `report["investigation"]` present, and that `persist_minted_case` is **not** called.

- [ ] TDD red → green → commit `feat: run_check uses agentic investigator; report carries investigation + proposed mint (D11)`.

---

### Task 3: Mint-on-approve (D12)

**Files:** Modify `agentci/engineer/mint.py` (add `approve_and_mint`); Test `tests/test_approve.py`.
```python
def approve_and_mint(report: dict, dataset_name: str | None = None) -> dict | None:
    """Persist the report's proposed minted case on human approval (D12). Returns the case or None."""
    case = report.get("proposed_mint")
    if not case:
        return None
    persist_minted_case(case, dataset_name)
    return case
```
Test: a report with `proposed_mint` → `persist_minted_case` called and the case returned (mock `_client`); a report without → returns None and not called.

- [ ] TDD red → green → commit `feat: mint eval case on human approval (D12)`.

---

### Task 4: CLI — `agentci check` (Change 6 surface)

**Files:** Create `agentci/cli.py`; Test `tests/test_cli.py`. (`pyproject` already wires `agentci = "agentci.cli:cli"`.)
```python
"""AgentCI command line: run a regression check on a candidate prompt."""
import json
from pathlib import Path

import click

from agentci.engineer import run_check

_GATE_MARK = {"green": "GREEN ✅", "red": "RED ⛔"}


@click.group()
def cli():
    """AgentCI — regression CI for AI agents."""


@cli.command()
@click.option("--candidate", "candidate", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Path to a candidate system-prompt .txt file.")
@click.option("--label", default=None, help="Run label (defaults to the candidate file stem).")
@click.option("--runs-dir", default="runs", help="Directory to write the run report JSON into.")
def check(candidate, label, runs_dir):
    """Run a regression check on a candidate prompt and write its report."""
    prompt = Path(candidate).read_text(encoding="utf-8").strip()
    label = label or Path(candidate).stem
    report = run_check(prompt, label)

    out_dir = Path(runs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{label}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    click.echo(f"candidate : {label}")
    click.echo(f"gate      : {_GATE_MARK.get(report['gate'], report['gate'])}")
    click.echo(f"verdict   : {report['verdict']}")
    if report["regression_detected"]:
        click.echo(f"flipped   : {report['flips']['pass_to_fail']}")
        if report.get("promotion"):
            click.echo(f"held-out  : {report['promotion']['reason']}")
    click.echo(f"mcp calls : {report['mcp_calls']}")
    click.echo(f"report    : {report_path}")
    click.echo(f"dashboard : http://127.0.0.1:8000/?run={label}")
```
Test (CliRunner, isolated filesystem, monkeypatch `agentci.cli.run_check` to return a canned report): assert exit 0, `runs/<label>.json` written with that report, and the gate line printed.

- [ ] TDD red → green → commit `feat: agentci check CLI`.

---

### Task 5: Dashboard API (FastAPI)

**Files:** Create `agentci/server/__init__.py`, `agentci/server/app.py`; Test `tests/test_server.py`.

Serves the run reports and the approve action; the static page is mounted at `/`.
```python
"""FastAPI dashboard: serves run reports and the approve (mint) action (D12/D14)."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agentci.engineer.mint import approve_and_mint

_RUNS_DIR = Path("runs")
_STATIC = Path(__file__).resolve().parent / "static"


def _load_report(label: str) -> dict:
    p = _RUNS_DIR / f"{label}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no run report for {label!r}")
    return json.loads(p.read_text(encoding="utf-8"))


def create_app() -> FastAPI:
    app = FastAPI(title="AgentCI")

    @app.get("/api/runs")
    def list_runs():
        return sorted(p.stem for p in _RUNS_DIR.glob("*.json")) if _RUNS_DIR.exists() else []

    @app.get("/api/report/{label}")
    def get_report(label: str):
        return _load_report(label)

    @app.post("/api/approve/{label}")
    def approve(label: str):
        report = _load_report(label)
        if report.get("gate") != "green" or not report.get("proposed_mint"):
            raise HTTPException(status_code=409, detail="nothing to approve (gate not green / no proposed mint)")
        minted = approve_and_mint(report)              # D12: human-triggered
        report["minted"] = minted
        (_RUNS_DIR / f"{label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"approved": True, "minted": minted}

    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
    return app


app = create_app()
```
Test (`fastapi.testclient.TestClient`, tmp cwd with a seeded `runs/<label>.json`, monkeypatch `approve_and_mint`): `GET /api/report/<label>` returns the report; `GET /api/report/missing` → 404; `POST /api/approve/<label>` on a green-with-proposed-mint report → 200 + calls approve; on a red report → 409.

- [ ] TDD red → green → commit `feat: dashboard API (report + approve endpoints)`.

---

### Task 6: Dashboard page — built backward from the demo beat (D14)

**Files:** Create `agentci/server/static/index.html` (single page, vanilla JS fetch).

Not unit-tested (design artifact). Must make the **one beat** land, top-to-bottom:
1. **The gotcha, side by side:** the candidate's fluent, confident, *wrong* refund answer next to the baseline's correct one (pulled from `flips`/`investigation` + the run report). Headline: "a human skimming five outputs would have approved the one on the left."
2. **The catch:** the gate chip (RED), the flipped case ids, and the investigator's `hypothesis` → `investigation_steps[]` (the MCP queries it chose) → `root_cause.summary`, in plain English.
3. **The proof:** held-out lift number + `promotion.reason`, and the `proposed_fix.rationale`.
4. **The decision:** Approve / Reject buttons → `POST /api/approve/<label>` (Approve mints the eval case, D12); a "MCP calls: N" badge evidencing load-bearing MCP (GAP-4).

Use the same restrained engineering-schematic aesthetic as `architecture.html` (paper bg, ink, single ember accent, Instrument Serif + JetBrains Mono).

- [ ] Build the page; load it against a seeded `runs/*.json`; commit `feat: dashboard page built around the demo beat (D14)`.

---

### Task 7: Manual live integration (credential-gated — deferred)

- [ ] Record baseline experiments + run the battery live in `record` mode (Plan 03 Task 12), which now also records the **investigator trajectory** fixtures.
- [ ] `uv run agentci check --candidate candidates/reg_refund.txt` → RED, investigator names the refund-window omission, proposes a fix, held-out lift proven, dashboard shows the beat.
- [ ] Confirm Phoenix shows phoenix-mcp tool spans for the investigator (GAP-4 proof); commit `.agentci_cache` fixtures.

---

## Self-review (Plan 05)

- **D11:** investigation is a genuine reason-act loop (open goal, agent-chosen MCP calls), not a script; determinism via recorded trajectory + cached `mcp_calls`.
- **D12:** `run_check` no longer auto-mints; the dashboard Approve triggers `approve_and_mint`.
- **D14:** the page is structured as gotcha → catch → proof → decision.
- **Determinism:** all LLM/agent/MCP calls go through the Plan-01 cache; offline tests use replay/mocks; live recording is the one manual step.

**Done when:** all pytest green (investigator parse/replay, run_check control flow, approve, CLI, server endpoints); `agentci check` writes a report and the dashboard renders the beat against a seeded report. Live trajectory recording remains the credential-gated manual step.
