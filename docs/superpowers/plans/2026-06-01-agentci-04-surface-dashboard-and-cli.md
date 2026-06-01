# AgentCI Plan 04 — Surface: CLI + Dashboard

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Depends on Plans 01–03** (`run_check`, `run_battery`, the report contract).

**Goal:** Ship the two surfaces from the spec: a `agentci check` CLI that triggers a run and prints a summary + dashboard link, and a web dashboard that renders one run report so a human can approve/reject — surfacing evidence for all four judging criteria (technical implementation, tracing, MCP, self-improvement loop).

**Architecture:** `cli.py` is a `click` group: `check` (single candidate), `battery` (all six), `serve` (launch dashboard). A run report is written to `runs/<label>.json`; the FastAPI app reads the latest report and serves a single static HTML page plus `/api/report`, `/api/approve`, `/api/reject`. Approve persists the promoted prompt to `promoted/<label>.txt` and confirms the minted eval case is in the dataset.

**Tech Stack:** click, FastAPI, Uvicorn, vanilla HTML/JS (no build step), pytest + FastAPI TestClient.

---

## File structure (this plan)

- Create `agentci/runstore.py` — write/read run reports under `runs/`.
- Create `agentci/cli.py` — `agentci check|battery|serve`.
- Create `agentci/server/__init__.py`
- Create `agentci/server/app.py` — FastAPI app + approve/reject.
- Create `agentci/server/static/index.html` — single-page dashboard.
- Tests under `tests/`.

---

### Task 1: Run store

**Files:**
- Create: `agentci/runstore.py`
- Test: `tests/test_runstore.py`

`save_report(report)` writes `runs/<candidate_label>.json` and updates `runs/latest.json`. `load_latest()` / `load_report(label)` read them back.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runstore.py
from agentci import runstore

def test_save_and_load_latest(tmp_path, monkeypatch):
    monkeypatch.setattr(runstore, "RUNS_DIR", tmp_path)
    report = {"candidate_label": "reg_refund.txt", "verdict": "green_promotable_fix", "gate": "green"}
    runstore.save_report(report)
    assert runstore.load_latest() == report
    assert runstore.load_report("reg_refund.txt") == report

def test_load_latest_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(runstore, "RUNS_DIR", tmp_path)
    assert runstore.load_latest() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_runstore.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.runstore'`.

- [ ] **Step 3: Write `agentci/runstore.py`**

```python
"""Persist and load AgentCI run reports for the CLI and dashboard."""
import json
from pathlib import Path

RUNS_DIR = Path("runs")


def _ensure() -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNS_DIR


def save_report(report: dict) -> Path:
    d = _ensure()
    label = report["candidate_label"]
    path = d / f"{label}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (d / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def load_report(label: str) -> dict | None:
    path = RUNS_DIR / f"{label}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_latest() -> dict | None:
    path = RUNS_DIR / "latest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_runstore.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/runstore.py tests/test_runstore.py
git commit -m "feat: run report store"
```

---

### Task 2: Summary formatter (pure)

**Files:**
- Create: `agentci/cli.py` (formatter this task; commands in Task 3)
- Test: `tests/test_cli_format.py`

`format_summary(report)` returns the terminal text the CLI prints — gate, verdict, flips, lift/n, MCP-call count.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_format.py
from agentci.cli import format_summary

def test_summary_red_no_fix_mentions_gate_and_reason():
    report = {"candidate_label": "reg_hard.txt", "gate": "red", "verdict": "red_no_fix",
              "regression_detected": True, "flips": {"pass_to_fail": ["t09"], "fail_to_pass": []},
              "cluster": {"label": "x"}, "proposed_fix": {"revised_prompt": "p", "rationale": "r"},
              "promotion": {"promotable": False, "lift": 0.01, "n": 16,
                            "heldout_regressions": 0, "reason": "insufficient lift"},
              "mcp_calls": 5}
    s = format_summary(report)
    assert "RED" in s and "reg_hard.txt" in s
    assert "insufficient lift" in s
    assert "n=16" in s

def test_summary_green_no_regression():
    report = {"candidate_label": "benign_reword.txt", "gate": "green",
              "verdict": "green_no_regression", "regression_detected": False,
              "flips": {"pass_to_fail": [], "fail_to_pass": []},
              "cluster": None, "proposed_fix": None, "promotion": None, "mcp_calls": 2}
    s = format_summary(report)
    assert "GREEN" in s and "no regression" in s.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_format.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.cli'`.

- [ ] **Step 3: Write the formatter into `agentci/cli.py`**

```python
"""AgentCI command-line interface."""
import json

import click

from agentci import runstore


def format_summary(report: dict) -> str:
    """Render a run report as terminal text."""
    gate = report["gate"].upper()
    lines = [
        f"AgentCI check: {report['candidate_label']}",
        f"  GATE: {gate}   verdict: {report['verdict']}",
    ]
    if not report["regression_detected"]:
        lines.append("  Result: no regression detected — gate stays green.")
    else:
        ptf = ", ".join(report["flips"]["pass_to_fail"]) or "-"
        lines.append(f"  Regression: {len(report['flips']['pass_to_fail'])} case(s) flipped pass->fail [{ptf}]")
        if report.get("cluster"):
            lines.append(f"  Cluster: {report['cluster'].get('label')}")
        promo = report.get("promotion") or {}
        if promo:
            lines.append(f"  Held-out lift: {promo.get('lift'):+.3f} (n={promo.get('n')}); {promo.get('reason')}")
    lines.append(f"  MCP calls (Phoenix introspection): {report.get('mcp_calls')}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_format.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/cli.py tests/test_cli_format.py
git commit -m "feat: CLI summary formatter"
```

---

### Task 3: CLI commands

**Files:**
- Modify: `agentci/cli.py` (append commands)
- Test: `tests/test_cli_commands.py`

`agentci check --candidate <file> [--label <l>]` runs `run_check`, saves the report, prints summary + dashboard URL. `agentci battery` runs all six and prints the confusion matrix. `agentci serve` launches the dashboard. We test `check` with `run_check` monkeypatched via Click's `CliRunner`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_commands.py
from click.testing import CliRunner
from agentci import cli, runstore

def test_check_command_runs_and_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(runstore, "RUNS_DIR", tmp_path)
    cand = tmp_path / "c.txt"
    cand.write_text("SOME PROMPT")
    fake = {"candidate_label": "c.txt", "gate": "green", "verdict": "green_no_regression",
            "regression_detected": False, "flips": {"pass_to_fail": [], "fail_to_pass": []},
            "cluster": None, "proposed_fix": None, "promotion": None, "mcp_calls": 2}
    monkeypatch.setattr(cli, "run_check", lambda prompt, label: fake)
    result = CliRunner().invoke(cli.cli, ["check", "--candidate", str(cand)])
    assert result.exit_code == 0
    assert "GREEN" in result.output
    assert runstore.load_report("c.txt") == fake

def test_check_red_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(runstore, "RUNS_DIR", tmp_path)
    cand = tmp_path / "c.txt"; cand.write_text("P")
    red = {"candidate_label": "c.txt", "gate": "red", "verdict": "red_no_fix",
           "regression_detected": True, "flips": {"pass_to_fail": ["t0"], "fail_to_pass": []},
           "cluster": {"label": "x"}, "proposed_fix": {"revised_prompt": "p", "rationale": "r"},
           "promotion": {"promotable": False, "lift": 0.0, "n": 16,
                         "heldout_regressions": 1, "reason": "held-out regression"},
           "mcp_calls": 4}
    monkeypatch.setattr(cli, "run_check", lambda prompt, label: red)
    result = CliRunner().invoke(cli.cli, ["check", "--candidate", str(cand)])
    assert result.exit_code == 1   # red gate => CI-style failure
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_commands.py -v`
Expected: FAIL with `AttributeError: module 'agentci.cli' has no attribute 'cli'`.

- [ ] **Step 3: Append commands to `agentci/cli.py`**

```python
import sys
from pathlib import Path

from agentci.engineer import run_check
from agentci.engineer.battery import run_battery

DASHBOARD_URL = "http://127.0.0.1:8000"


@click.group()
def cli() -> None:
    """AgentCI — regression CI for AI agents."""


@cli.command()
@click.option("--candidate", "candidate", required=True, type=click.Path(exists=True),
              help="Path to a candidate system-prompt file.")
@click.option("--label", default=None, help="Run label (defaults to candidate filename).")
def check(candidate: str, label: str | None) -> None:
    """Run AgentCI on one candidate prompt."""
    label = label or Path(candidate).name
    prompt = Path(candidate).read_text(encoding="utf-8").strip()
    report = run_check(prompt, label)
    runstore.save_report(report)
    click.echo(format_summary(report))
    click.echo(f"  Dashboard: {DASHBOARD_URL}  (run `agentci serve`)")
    sys.exit(0 if report["gate"] == "green" else 1)


@cli.command()
def battery() -> None:
    """Run the full labeled candidate battery and print the confusion matrix."""
    result = run_battery()
    for report in result["reports"].values():
        runstore.save_report(report)
    cm = result["confusion"]
    click.echo(f"Battery confusion: TP={cm['tp']} FP={cm['fp']} TN={cm['tn']} FN={cm['fn']} "
               f"(false-positive rate {cm['false_positive_rate']})")
    sys.exit(0 if cm["fp"] == 0 and cm["fn"] == 0 else 1)


@cli.command()
@click.option("--port", default=8000)
def serve(port: int) -> None:
    """Launch the AgentCI dashboard."""
    import uvicorn
    uvicorn.run("agentci.server.app:app", host="127.0.0.1", port=port)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_commands.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/cli.py tests/test_cli_commands.py
git commit -m "feat: agentci check/battery/serve commands"
```

---

### Task 4: Dashboard API (FastAPI) + approve/reject

**Files:**
- Create: `agentci/server/__init__.py`
- Create: `agentci/server/app.py`
- Test: `tests/test_server.py`

`GET /api/report` returns the latest report. `POST /api/approve` persists the promoted prompt to `promoted/<label>.txt` (only if gate green + fix present) and returns `{"approved": true}`. `POST /api/reject` returns `{"approved": false}`. `GET /` serves the static page.

- [ ] **Step 1: Write `agentci/server/__init__.py`**

```python
```

(empty)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_server.py
from fastapi.testclient import TestClient
from agentci import runstore
from agentci.server import app as appmod

def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(runstore, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(appmod, "PROMOTED_DIR", tmp_path / "promoted")
    return TestClient(appmod.app)

def test_get_report_returns_latest(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    runstore.save_report({"candidate_label": "reg_refund.txt", "gate": "green",
                          "verdict": "green_promotable_fix",
                          "proposed_fix": {"revised_prompt": "FIXED PROMPT", "rationale": "r"}})
    r = client.get("/api/report")
    assert r.status_code == 200 and r.json()["candidate_label"] == "reg_refund.txt"

def test_approve_persists_promoted_prompt(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    runstore.save_report({"candidate_label": "reg_refund.txt", "gate": "green",
                          "verdict": "green_promotable_fix",
                          "proposed_fix": {"revised_prompt": "FIXED PROMPT", "rationale": "r"}})
    r = client.post("/api/approve")
    assert r.status_code == 200 and r.json()["approved"] is True
    assert (appmod.PROMOTED_DIR / "reg_refund.txt").read_text() == "FIXED PROMPT"

def test_approve_blocked_when_red(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    runstore.save_report({"candidate_label": "x", "gate": "red", "verdict": "red_no_fix",
                          "proposed_fix": {"revised_prompt": "p", "rationale": "r"}})
    r = client.post("/api/approve")
    assert r.status_code == 409   # cannot promote a red gate
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.server.app'`.

- [ ] **Step 4: Write `agentci/server/app.py`**

```python
"""FastAPI dashboard: serves the latest run report and the approve/reject gate."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from agentci import runstore

app = FastAPI(title="AgentCI")
_STATIC = Path(__file__).resolve().parent / "static"
PROMOTED_DIR = Path("promoted")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


@app.get("/api/report")
def get_report() -> JSONResponse:
    report = runstore.load_latest()
    if report is None:
        raise HTTPException(status_code=404, detail="no runs yet")
    return JSONResponse(report)


@app.post("/api/approve")
def approve() -> JSONResponse:
    report = runstore.load_latest()
    if report is None:
        raise HTTPException(status_code=404, detail="no runs yet")
    if report["gate"] != "green":
        raise HTTPException(status_code=409, detail="cannot promote a red gate")
    fix = report.get("proposed_fix")
    PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
    prompt = fix["revised_prompt"] if fix else ""
    (PROMOTED_DIR / report["candidate_label"]).write_text(prompt, encoding="utf-8")
    return JSONResponse({"approved": True, "candidate_label": report["candidate_label"]})


@app.post("/api/reject")
def reject() -> JSONResponse:
    report = runstore.load_latest()
    if report is None:
        raise HTTPException(status_code=404, detail="no runs yet")
    return JSONResponse({"approved": False, "candidate_label": report["candidate_label"]})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add agentci/server/__init__.py agentci/server/app.py tests/test_server.py
git commit -m "feat: dashboard API with approve/reject gate"
```

---

### Task 5: Dashboard page (evidences all four criteria)

**Files:**
- Create: `agentci/server/static/index.html`
- Test: `tests/test_static.py`

The page fetches `/api/report` and renders five evidence blocks mapped to the judging criteria: (1) gate/verdict banner [self-improvement loop], (2) flips + cluster + prompt diff [loop], (3) before/after held-out lift with n [loop/honesty], (4) MCP-call count [MCP], (5) a link/note to the Phoenix trace [tracing] — plus Approve/Reject buttons. We test that the file contains the wiring (static assertions; full visual check is the manual step).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_static.py
from pathlib import Path

HTML = Path("agentci/server/static/index.html").read_text(encoding="utf-8")

def test_page_wires_api_and_actions():
    assert "/api/report" in HTML
    assert "/api/approve" in HTML and "/api/reject" in HTML

def test_page_renders_four_criteria_evidence():
    for marker in ["data-evidence=\"loop\"", "data-evidence=\"mcp\"",
                   "data-evidence=\"tracing\"", "data-evidence=\"lift\""]:
        assert marker in HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_static.py -v`
Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Write `agentci/server/static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AgentCI</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 0; background: #0b0e14; color: #e6e6e6; }
    header { padding: 16px 24px; border-bottom: 1px solid #232a36; }
    main { max-width: 920px; margin: 0 auto; padding: 24px; display: grid; gap: 16px; }
    .card { background: #131722; border: 1px solid #232a36; border-radius: 10px; padding: 16px; }
    .banner { font-size: 22px; font-weight: 700; padding: 14px 16px; border-radius: 10px; }
    .green { background: #11321f; color: #6ee7a8; border: 1px solid #1f7a4d; }
    .red { background: #3a1414; color: #ff9b9b; border: 1px solid #a13030; }
    .row { display: flex; gap: 24px; flex-wrap: wrap; }
    .stat { font-size: 28px; font-weight: 700; }
    .muted { color: #8b93a7; font-size: 13px; }
    pre { white-space: pre-wrap; background: #0b0e14; padding: 12px; border-radius: 8px; border: 1px solid #232a36; }
    button { padding: 10px 18px; border-radius: 8px; border: 0; font-weight: 600; cursor: pointer; }
    .approve { background: #1f7a4d; color: white; } .reject { background: #a13030; color: white; }
    h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em; color: #8b93a7; margin: 0 0 8px; }
  </style>
</head>
<body>
  <header><strong>AgentCI</strong> — regression CI for AI agents</header>
  <main>
    <div id="banner" class="banner">Loading…</div>

    <div class="card" data-evidence="loop">
      <h2>Regression &amp; failure cluster</h2>
      <div id="flips" class="muted"></div>
      <div id="cluster"></div>
    </div>

    <div class="card" data-evidence="loop">
      <h2>Proposed prompt fix</h2>
      <pre id="fix">—</pre>
      <div id="rationale" class="muted"></div>
    </div>

    <div class="card" data-evidence="lift">
      <h2>Held-out lift (honest, n stated)</h2>
      <div class="row">
        <div><div class="stat" id="lift">—</div><div class="muted">held-out correctness lift</div></div>
        <div><div class="stat" id="n">—</div><div class="muted">held-out cases (n)</div></div>
        <div><div class="stat" id="hreg">—</div><div class="muted">held-out regressions</div></div>
      </div>
      <div id="liftreason" class="muted"></div>
    </div>

    <div class="card" data-evidence="mcp">
      <h2>Phoenix MCP usage (runtime introspection)</h2>
      <div class="stat" id="mcp">—</div>
      <div class="muted">MCP tool calls the Engineer made to read baseline results from Phoenix.</div>
    </div>

    <div class="card" data-evidence="tracing">
      <h2>Tracing</h2>
      <div class="muted">The Engineer and target runs are OpenInference-instrumented; open your Phoenix
      space to inspect the spans for this run (project <code>agentci</code>).</div>
    </div>

    <div class="card">
      <button class="approve" id="approve">Approve &amp; promote</button>
      <button class="reject" id="reject">Reject</button>
      <div id="outcome" class="muted"></div>
    </div>
  </main>

  <script>
    async function load() {
      const res = await fetch("/api/report");
      if (!res.ok) { document.getElementById("banner").textContent = "No runs yet."; return; }
      const r = await res.json();
      const banner = document.getElementById("banner");
      banner.textContent = `${r.candidate_label} — ${r.gate.toUpperCase()} (${r.verdict})`;
      banner.className = "banner " + (r.gate === "green" ? "green" : "red");

      const ptf = (r.flips && r.flips.pass_to_fail) || [];
      document.getElementById("flips").textContent =
        r.regression_detected ? `${ptf.length} case(s) flipped pass→fail: ${ptf.join(", ")}` : "No regression detected.";
      document.getElementById("cluster").textContent = r.cluster ? `Cluster: ${r.cluster.label}` : "";

      document.getElementById("fix").textContent = r.proposed_fix ? r.proposed_fix.revised_prompt : "—";
      document.getElementById("rationale").textContent = r.proposed_fix ? r.proposed_fix.rationale : "";

      const p = r.promotion || {};
      document.getElementById("lift").textContent = (p.lift ?? "—");
      document.getElementById("n").textContent = (p.n ?? "—");
      document.getElementById("hreg").textContent = (p.heldout_regressions ?? "—");
      document.getElementById("liftreason").textContent = p.reason || "";

      document.getElementById("mcp").textContent = (r.mcp_calls ?? "—");
    }
    async function act(path) {
      const res = await fetch(path, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      document.getElementById("outcome").textContent =
        res.ok ? (body.approved ? "Approved — prompt promoted, eval case persisted." : "Rejected.")
               : ("Blocked: " + (body.detail || res.status));
    }
    document.getElementById("approve").onclick = () => act("/api/approve");
    document.getElementById("reject").onclick = () => act("/api/reject");
    load();
  </script>
</body>
</html>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_static.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/server/static/index.html tests/test_static.py
git commit -m "feat: dashboard page evidencing all four judging criteria"
```

---

### Task 6: Full-suite test pass + manual demo dry run

- [ ] **Step 1: Run the whole test suite**

Run: `uv run pytest -v`
Expected: all tests across Plans 01–04 PASS.

- [ ] **Step 2: Replay the headline candidate end-to-end (deterministic, uses recorded fixtures)**

```bash
# AGENTCI_CACHE_MODE=replay (default) so this uses the fixtures recorded in Plan 03
uv run agentci check --candidate candidates/reg_refund.txt
```

Expected: prints regression caught on refund cases, a promotable held-out lift with `n=16`, MCP call count > 0, GATE GREEN, dashboard URL. Exit code 0.

- [ ] **Step 3: Launch the dashboard and walk the demo**

```bash
uv run agentci serve
```

Open `http://127.0.0.1:8000`. Expected: green banner, flip list + refund cluster, prompt diff, before/after lift with n, MCP-call stat, tracing note; Approve writes `promoted/reg_refund.txt`.

- [ ] **Step 4: Verify the no-fix RED path is demoable**

Run: `uv run agentci check --candidate candidates/reg_routing.txt` (or whichever regressive candidate the Plan-03 battery recorded as `red_no_fix`).
Expected: if that candidate's fix did not clear the gate, RED banner with the honest reason and Approve blocked (HTTP 409). This is the GAP-6 credibility moment.

- [ ] **Step 5: Commit any fixtures/promoted artifacts produced**

```bash
git add runs/ promoted/ .agentci_cache
git commit -m "test: end-to-end demo dry run artifacts"
```

---

## Self-review (Plan 04)

- **Spec coverage:** `agentci check` CLI ✓ (§4.C), dashboard with regression summary / cluster / prompt diff / before-after bars / approve-reject ✓ (§4.C), human gate persists promoted prompt + eval case ✓ (§5.8), red gate blocks promotion ✓ (GAP-6). All four judging criteria have an explicit evidence block (`data-evidence` markers).
- **Placeholder scan:** none. Static-assertion tests intentionally check wiring, not visuals (visual check is the manual Task 6 step) — not a placeholder.
- **Type consistency:** consumes the exact Plan-03 report contract (`gate`, `verdict`, `regression_detected`, `flips.pass_to_fail`, `cluster.label`, `proposed_fix.revised_prompt/rationale`, `promotion.lift/n/heldout_regressions/reason`, `mcp_calls`). `runstore.RUNS_DIR` and `app.PROMOTED_DIR` are monkeypatch points used by tests.

**Done when:** `uv run pytest -v` is fully green AND the manual replay shows a green promotable run + a red no-fix run on the dashboard with Approve correctly gated.
