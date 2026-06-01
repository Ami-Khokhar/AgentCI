# AgentCI Plan 03 — Engineer Loop + Phoenix MCP

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Depends on Plans 01 & 02** (`config`, `cache`, `answer_ticket`, `run_candidate`, the Phoenix dataset + baseline experiment).

**Goal:** Build the Engineer agent that, for a candidate prompt, reads the baseline experiment **through the Phoenix MCP server** (load-bearing MCP, GAP-4), detects pass→fail flips (D10), clusters the failure, drafts a fix, mints a permanent eval case into the tune partition (D5), proves held-out lift behind the promotion gate (D8), and refuses to promote when no fix qualifies. Then run the full 6-candidate battery (D4) into a confusion matrix (GAP-1/GAP-2).

**Architecture:** `engineer/agent.py` is an ADK `LlmAgent` whose `tools` include `@arizeai/phoenix-mcp` mounted as an `McpToolset` (D1) — this is how the Engineer fetches baseline results at runtime. Pure decision logic (flip detection, lift math, gate, confusion matrix) lives in separate modules and is unit-tested directly; MCP/LLM calls go through the Plan-01 cache.

**Tech Stack:** google-adk (`McpToolset`, `StdioConnectionParams`), `@arizeai/phoenix-mcp` via npx (Node.js required), arize-phoenix-client (fallback path), pytest (+ Plans 01–02 stack).

---

## File structure (this plan)

- Create `agentci/engineer/__init__.py`
- Create `agentci/engineer/agent.py` — ADK Engineer agent + phoenix `McpToolset` (D1).
- Create `agentci/engineer/compare.py` — fetch baseline per-case **via MCP**, diff → flips (GAP-4, D10).
- Create `agentci/engineer/cluster.py` — LLM clustering of flipped/failing cases.
- Create `agentci/engineer/fix.py` — draft a revised prompt targeting the cluster.
- Create `agentci/engineer/mint.py` — mint a new eval case into the tune partition (D5).
- Create `agentci/engineer/lift.py` — held-out lift + promotion gate (D8).
- Create `agentci/engineer/battery.py` — run 6 labeled candidates → confusion matrix (D4/GAP-1/2).
- Create `agentci/engineer/report.py` — assemble the run report JSON (consumed by Plan 04).
- Create `candidates/*.txt` + `candidates/labels.json` — the 6 battery candidates (D4).
- Tests under `tests/`.

---

### Task 1: Flip detection (the regression signal, D10)

**Files:**
- Create: `agentci/engineer/__init__.py`
- Create: `agentci/engineer/compare.py` (diff logic this task; MCP fetch in Task 2)
- Test: `tests/test_flips.py`

A "flip" compares a baseline per-case row to a candidate per-case row **for the same id**. `pass_to_fail` = baseline passed AND candidate failed. `fail_to_pass` = reverse. A candidate is **flagged as a regression** iff ≥1 tune-partition `pass_to_fail` flip (D10).

- [ ] **Step 1: Write `agentci/engineer/__init__.py`**

```python
```

(empty)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_flips.py
from agentci.engineer.compare import compute_flips, is_regression

def _row(id, split, passed, corr=0.9):
    return {"id": id, "split": split, "passed": passed,
            "scores": {"correctness": corr, "groundedness": 0.9,
                       "completeness": 0.9, "policy_reference": 0.9}}

def test_compute_flips_detects_both_directions():
    base = [_row("t00", "tune", True), _row("t01", "tune", False)]
    cand = [_row("t00", "tune", False), _row("t01", "tune", True)]
    flips = compute_flips(base, cand)
    assert flips["pass_to_fail"] == ["t00"]
    assert flips["fail_to_pass"] == ["t01"]

def test_is_regression_true_on_any_tune_pass_to_fail():
    base = [_row("t00", "tune", True)]
    cand = [_row("t00", "tune", False)]
    assert is_regression(base, cand) is True

def test_is_regression_ignores_heldout_flips_for_flagging():
    base = [_row("h0", "held_out", True)]
    cand = [_row("h0", "held_out", False)]
    assert is_regression(base, cand) is False  # flagging is tune-only (D10)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_flips.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.compare'`.

- [ ] **Step 4: Write diff logic into `agentci/engineer/compare.py`**

```python
"""Compare candidate vs baseline per-case results. Baseline is fetched THROUGH Phoenix MCP."""


def _index(rows: list[dict]) -> dict:
    return {r["id"]: r for r in rows}


def compute_flips(baseline: list[dict], candidate: list[dict]) -> dict:
    """Return {'pass_to_fail': [ids], 'fail_to_pass': [ids]} over ids present in both."""
    b, c = _index(baseline), _index(candidate)
    ptf, ftp = [], []
    for cid in sorted(b.keys() & c.keys()):
        if b[cid]["passed"] and not c[cid]["passed"]:
            ptf.append(cid)
        elif not b[cid]["passed"] and c[cid]["passed"]:
            ftp.append(cid)
    return {"pass_to_fail": ptf, "fail_to_pass": ftp}


def is_regression(baseline: list[dict], candidate: list[dict]) -> bool:
    """A candidate is flagged iff >=1 TUNE-partition pass->fail flip (D10)."""
    tune_base = [r for r in baseline if r["split"] == "tune"]
    tune_cand = [r for r in candidate if r["split"] == "tune"]
    return len(compute_flips(tune_base, tune_cand)["pass_to_fail"]) > 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_flips.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add agentci/engineer/__init__.py agentci/engineer/compare.py tests/test_flips.py
git commit -m "feat: pass/fail flip detection and regression flag (D10)"
```

---

### Task 2: Engineer agent with Phoenix MCP toolset (D1)

**Files:**
- Create: `agentci/engineer/agent.py`
- Test: `tests/test_engineer_agent.py`

The Engineer is an `LlmAgent` whose tools include the Phoenix MCP server via `McpToolset`. We test that the toolset is wired with the correct `npx` command and Phoenix credentials from env — not a live MCP call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engineer_agent.py
from agentci.engineer import agent as eng
from agentci import config

def test_phoenix_mcp_stdio_params(monkeypatch):
    monkeypatch.setenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com/s/demo")
    monkeypatch.setenv("PHOENIX_API_KEY", "px_live_test")
    params = eng.phoenix_mcp_server_params()
    assert params.command == "npx"
    assert "@arizeai/phoenix-mcp@latest" in params.args
    assert "--baseUrl" in params.args and "https://app.phoenix.arize.com/s/demo" in params.args
    assert "--apiKey" in params.args and "px_live_test" in params.args

def test_engineer_uses_pinned_model_and_mcp_toolset(monkeypatch):
    monkeypatch.setenv("PHOENIX_BASE_URL", "https://x")
    monkeypatch.setenv("PHOENIX_API_KEY", "k")
    a = eng.build_engineer_agent()
    assert a.model == config.ENGINEER_MODEL
    assert len(a.tools) >= 1  # the McpToolset
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_engineer_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.agent'`.

- [ ] **Step 3: Write `agentci/engineer/agent.py`**

```python
"""The Engineer agent: an ADK LlmAgent that introspects Phoenix at runtime via MCP (D1)."""
import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from agentci import config

ENGINEER_INSTRUCTION = """You are AgentCI's reliability engineer. You have Phoenix tools
(via MCP) to read experiments, datasets, traces, and per-case annotations. When asked to
compare a candidate to a baseline, fetch the baseline experiment's per-case scores THROUGH
the Phoenix MCP tools — never assume them. Return structured JSON when asked."""


def phoenix_mcp_server_params() -> StdioServerParameters:
    """Stdio params that launch @arizeai/phoenix-mcp against this Phoenix space."""
    return StdioServerParameters(
        command="npx",
        args=[
            "-y", "@arizeai/phoenix-mcp@latest",
            "--baseUrl", os.environ["PHOENIX_BASE_URL"],
            "--apiKey", os.environ["PHOENIX_API_KEY"],
        ],
    )


def build_engineer_agent() -> LlmAgent:
    """Build the Engineer with the Phoenix MCP server mounted as a toolset (in-process client)."""
    phoenix_tools = McpToolset(
        connection_params=StdioConnectionParams(server_params=phoenix_mcp_server_params())
    )
    return LlmAgent(
        name="agentci_engineer",
        model=config.ENGINEER_MODEL,
        description="Detects regressions, root-causes, and proposes fixes for target agents.",
        instruction=ENGINEER_INSTRUCTION,
        tools=[phoenix_tools],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_engineer_agent.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/agent.py tests/test_engineer_agent.py
git commit -m "feat: Engineer agent with Phoenix MCP toolset (D1)"
```

---

### Task 3: Fetch baseline per-case THROUGH MCP (load-bearing MCP, GAP-4)

**Files:**
- Modify: `agentci/engineer/compare.py` (append `fetch_baseline_via_mcp`)
- Test: `tests/test_fetch_baseline.py`

The Engineer agent is driven with a prompt instructing it to use Phoenix MCP tools to return the baseline experiment's per-case rows as JSON. The function parses that into the standard per-case row shape. **The Engineer holds no local copy of the baseline** — it must read it via MCP (GAP-4). Cached for determinism; tested via replay.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_baseline.py
import json
from agentci import cache
from agentci.engineer import compare

def test_fetch_baseline_parses_mcp_json(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"experiment_name": "baseline-tune"}
    rows = [{"id": "t00", "split": "tune", "passed": True,
             "scores": {"correctness": 0.9, "groundedness": 0.9,
                        "completeness": 0.9, "policy_reference": 0.9}}]
    (tmp_path / (cache._key("mcp_baseline", payload) + ".json")).write_text(json.dumps(rows))
    out = compare.fetch_baseline_via_mcp("baseline-tune")
    assert out == rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetch_baseline.py -v`
Expected: FAIL with `AttributeError: module 'agentci.engineer.compare' has no attribute 'fetch_baseline_via_mcp'`.

- [ ] **Step 3: Append to `agentci/engineer/compare.py`**

```python
import asyncio
import json as _json
import uuid as _uuid

from agentci import cache


async def _ask_engineer_for_baseline(experiment_name: str) -> str:
    """Drive the Engineer agent to fetch baseline per-case scores via Phoenix MCP."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-engineer")
    uid, sid = "agentci", _uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-engineer", user_id=uid, session_id=sid
    )
    prompt = (
        f"Using the Phoenix MCP tools, fetch experiment '{experiment_name}'. For each example "
        f"return its metadata id, split, the four annotation scores "
        f"(correctness, groundedness, completeness, policy_reference), and whether it passed "
        f"(all four >= {0.7}). Return ONLY a JSON array of objects with keys "
        f'"id","split","passed","scores".'
    )
    final = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def fetch_baseline_via_mcp(experiment_name: str) -> list[dict]:
    """Return baseline per-case rows, read at runtime THROUGH Phoenix MCP (GAP-4). Cached (D7)."""
    payload = {"experiment_name": experiment_name}

    def live():
        raw = asyncio.run(_ask_engineer_for_baseline(experiment_name))
        text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return _json.loads(text)

    return cache.cached("mcp_baseline", payload, live)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fetch_baseline.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/compare.py tests/test_fetch_baseline.py
git commit -m "feat: fetch baseline per-case scores through Phoenix MCP (GAP-4)"
```

---

### Task 4: Failure clustering

**Files:**
- Create: `agentci/engineer/cluster.py`
- Test: `tests/test_cluster.py`

Given the failing cases' questions, gold resolutions, and candidate answers, an LLM returns a single dominant failure cluster: `{"label": str, "policy_id": str, "summary": str, "case_ids": [...]}`. Cached. We test the prompt-payload assembly and parsing via replay.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cluster.py
import json
from agentci import cache
from agentci.engineer import cluster

def test_cluster_failures_parses_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    cases = [{"id": "t05", "question": "refund?", "gold": "14 days", "answer": "no refunds"}]
    payload = {"cases": cases}
    result = {"label": "refund-policy", "policy_id": "refund-policy",
              "summary": "drops refund window", "case_ids": ["t05"]}
    (tmp_path / (cache._key("cluster", payload) + ".json")).write_text(json.dumps(result))
    out = cluster.cluster_failures(cases)
    assert out["label"] == "refund-policy"
    assert out["case_ids"] == ["t05"]

def test_cluster_failures_empty_returns_none():
    assert cluster.cluster_failures([]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cluster.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.cluster'`.

- [ ] **Step 3: Write `agentci/engineer/cluster.py`**

```python
"""Cluster the regressed cases into one dominant failure pattern (LLM-as-analyst)."""
import json

from google import genai

from agentci import cache, config


def cluster_failures(cases: list[dict]) -> dict | None:
    """Return the dominant failure cluster for the given failing cases, or None if empty.

    Each case: {"id","question","gold","answer"}.
    Returns: {"label","policy_id","summary","case_ids"}.
    """
    if not cases:
        return None
    payload = {"cases": cases}

    def live():
        client = genai.Client()
        prompt = (
            "These support cases regressed (candidate answer is wrong vs gold). "
            "Identify the SINGLE dominant failure cluster.\n\n"
            f"{json.dumps(cases, indent=2)}\n\n"
            'Return ONLY JSON: {"label": "<short>", "policy_id": "<kb id>", '
            '"summary": "<one sentence>", "case_ids": ["..."]}'
        )
        resp = client.models.generate_content(
            model=config.ENGINEER_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    return cache.cached("cluster", payload, live)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cluster.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/cluster.py tests/test_cluster.py
git commit -m "feat: LLM failure clustering"
```

---

### Task 5: Draft the prompt fix

**Files:**
- Create: `agentci/engineer/fix.py`
- Test: `tests/test_fix.py`

`draft_fix(candidate_prompt, cluster)` returns a revised prompt that targets the cluster while preserving the candidate's intent (e.g. keep token savings). Cached; returns `{"revised_prompt": str, "rationale": str}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fix.py
import json
from agentci import cache
from agentci.engineer import fix

def test_draft_fix_parses_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    cluster = {"label": "refund-policy", "policy_id": "refund-policy",
               "summary": "drops refund window", "case_ids": ["t05"]}
    payload = {"candidate_prompt": "SHORT PROMPT", "cluster": cluster}
    result = {"revised_prompt": "SHORT PROMPT + state refund window",
              "rationale": "restores refund detail, keeps brevity"}
    (tmp_path / (cache._key("fix", payload) + ".json")).write_text(json.dumps(result))
    out = fix.draft_fix("SHORT PROMPT", cluster)
    assert "refund" in out["revised_prompt"].lower()
    assert out["rationale"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fix.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.fix'`.

- [ ] **Step 3: Write `agentci/engineer/fix.py`**

```python
"""Draft a revised system prompt targeting the failure cluster, preserving candidate intent."""
import json

from google import genai

from agentci import cache, config


def draft_fix(candidate_prompt: str, cluster: dict) -> dict:
    """Return {"revised_prompt", "rationale"} fixing `cluster` while keeping candidate intent."""
    payload = {"candidate_prompt": candidate_prompt, "cluster": cluster}

    def live():
        client = genai.Client()
        prompt = (
            "A candidate support-agent system prompt caused a regression cluster. "
            "Revise the prompt to FIX the cluster while preserving the candidate's intent "
            "(e.g. brevity/token savings). Do not over-correct other behaviors.\n\n"
            f"CANDIDATE PROMPT:\n{candidate_prompt}\n\n"
            f"FAILURE CLUSTER:\n{json.dumps(cluster, indent=2)}\n\n"
            'Return ONLY JSON: {"revised_prompt": "<full new prompt>", "rationale": "<why>"}'
        )
        resp = client.models.generate_content(
            model=config.ENGINEER_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    return cache.cached("fix", payload, live)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fix.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/fix.py tests/test_fix.py
git commit -m "feat: prompt-fix drafting targeting the failure cluster"
```

---

### Task 6: Mint a new eval case (tune partition only, D5)

**Files:**
- Create: `agentci/engineer/mint.py`
- Test: `tests/test_mint.py`

`mint_eval_case(cluster)` builds a new ticket capturing the failure (a sharpened question + gold from the KB section), tags it `split="tune"`, `source="minted"` (D5), and appends it to the Phoenix dataset. We test the case construction (pure) and mock the dataset append.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mint.py
from unittest.mock import MagicMock
from agentci.engineer import mint

def test_minted_case_is_tune_and_minted_source():
    case = mint.build_minted_case(
        cluster={"label": "refund-policy", "policy_id": "refund-policy",
                 "summary": "drops refund window", "case_ids": ["t05"]},
        question="Exactly how many days do I have to request a refund?",
        gold="You have 14 days from the charge; monthly plans only.",
    )
    assert case["split"] == "tune"        # D5: never held_out
    assert case["source"] == "minted"
    assert case["policy_id"] == "refund-policy"
    assert case["id"].startswith("minted-")

def test_persist_minted_case_appends_to_dataset(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(mint, "_client", lambda: client)
    case = {"id": "minted-refund-policy-0", "question": "q", "gold_resolution": "g",
            "policy_id": "refund-policy", "split": "tune", "source": "minted", "kb": "KB"}
    mint.persist_minted_case(case)
    assert client.datasets.add_examples_to_dataset.called or client.datasets.create_dataset.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.mint'`.

- [ ] **Step 3: Write `agentci/engineer/mint.py`**

```python
"""Mint a permanent eval case capturing the caught regression. Tune partition only (D5)."""
import json
from pathlib import Path

import pandas as pd
from phoenix.client import Client

from agentci import config

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "kb.json"


def _kb_text() -> str:
    return json.dumps(json.loads(_KB_PATH.read_text(encoding="utf-8")))


def build_minted_case(cluster: dict, question: str, gold: str, index: int = 0) -> dict:
    """Construct the new eval case row. Always split='tune', source='minted' (D5)."""
    label = cluster["label"]
    return {
        "id": f"minted-{label}-{index}",
        "question": question,
        "gold_resolution": gold,
        "policy_id": cluster["policy_id"],
        "split": "tune",
        "source": "minted",
        "kb": _kb_text(),
    }


def _client() -> Client:
    return Client()


def persist_minted_case(case: dict, dataset_name: str | None = None) -> None:
    """Append the minted case to the Phoenix dataset so it permanently guards the failure."""
    df = pd.DataFrame([case])
    client = _client()
    client.datasets.add_examples_to_dataset(
        dataset=dataset_name or config.DATASET_NAME,
        dataframe=df,
        input_keys=["question"],
        output_keys=["gold_resolution"],
        metadata_keys=["policy_id", "split", "source", "kb", "id"],
    )
```

> Confirm the append method name (`add_examples_to_dataset`) and signature against the installed `arize-phoenix-client`. If the client only supports `create_dataset` with a version bump, append by re-creating with the grown dataframe. Keep `build_minted_case`'s row shape exactly (D5 tags are load-bearing for the held-out guarantee).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mint.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/mint.py tests/test_mint.py
git commit -m "feat: mint eval case into tune partition (D5)"
```

---

### Task 7: Held-out lift + promotion gate (D8)

**Files:**
- Create: `agentci/engineer/lift.py`
- Test: `tests/test_lift.py`

`evaluate_promotion(baseline_heldout, fixed_heldout)` computes mean-correctness lift and counts held-out pass→fail flips, then applies D8: promotable iff `lift >= 0.05` AND zero held-out pass→fail flips. Returns `{"lift","n","heldout_regressions","promotable","reason"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lift.py
from agentci.engineer.lift import mean_correctness, evaluate_promotion

def _r(id, passed, corr):
    return {"id": id, "split": "held_out", "passed": passed,
            "scores": {"correctness": corr, "groundedness": 0.9,
                       "completeness": 0.9, "policy_reference": 0.9}}

def test_mean_correctness():
    assert mean_correctness([_r("h0", True, 0.8), _r("h1", True, 0.6)]) == 0.7

def test_promotable_when_lift_and_no_regressions():
    base = [_r("h0", True, 0.6), _r("h1", True, 0.6)]
    fixed = [_r("h0", True, 0.9), _r("h1", True, 0.9)]
    out = evaluate_promotion(base, fixed)
    assert out["lift"] == 0.3 and out["heldout_regressions"] == 0
    assert out["promotable"] is True and out["n"] == 2

def test_not_promotable_when_heldout_regression():
    base = [_r("h0", True, 0.9)]
    fixed = [_r("h0", False, 0.4)]   # pass->fail on held-out
    out = evaluate_promotion(base, fixed)
    assert out["heldout_regressions"] == 1
    assert out["promotable"] is False

def test_not_promotable_when_lift_too_small():
    base = [_r("h0", True, 0.80)]
    fixed = [_r("h0", True, 0.82)]   # +0.02 < 0.05
    out = evaluate_promotion(base, fixed)
    assert out["promotable"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lift.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.lift'`.

- [ ] **Step 3: Write `agentci/engineer/lift.py`**

```python
"""Held-out lift computation and the promotion gate (D8)."""
from agentci import config
from agentci.engineer.compare import compute_flips


def mean_correctness(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return round(sum(r["scores"]["correctness"] for r in rows) / len(rows), 4)


def evaluate_promotion(baseline_heldout: list[dict], fixed_heldout: list[dict]) -> dict:
    """Apply D8: promotable iff held-out correctness lift >= MIN_HELDOUT_LIFT AND zero
    held-out pass->fail flips. Returns the full decision record."""
    lift = round(mean_correctness(fixed_heldout) - mean_correctness(baseline_heldout), 4)
    regressions = len(compute_flips(baseline_heldout, fixed_heldout)["pass_to_fail"])
    promotable = lift >= config.MIN_HELDOUT_LIFT and regressions <= config.MAX_HELDOUT_REGRESSIONS
    if promotable:
        reason = f"held-out lift {lift:+.3f} >= {config.MIN_HELDOUT_LIFT}, no held-out regressions"
    elif regressions > config.MAX_HELDOUT_REGRESSIONS:
        reason = f"{regressions} held-out pass->fail flip(s) — gate stays RED"
    else:
        reason = f"held-out lift {lift:+.3f} < {config.MIN_HELDOUT_LIFT} — insufficient, gate stays RED"
    return {
        "lift": lift,
        "n": len(fixed_heldout),
        "heldout_regressions": regressions,
        "promotable": promotable,
        "reason": reason,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_lift.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/lift.py tests/test_lift.py
git commit -m "feat: held-out lift and promotion gate (D8)"
```

---

### Task 8: Run report assembly + the "no-fix → RED" path (GAP-6)

**Files:**
- Create: `agentci/engineer/report.py`
- Test: `tests/test_report.py`

`assemble_report(...)` produces the single JSON object the dashboard/CLI consume. It encodes every terminal outcome including **regression confirmed, no qualifying fix → gate RED** (GAP-6). `verdict` ∈ `{"green_no_regression", "green_promotable_fix", "red_no_fix"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from agentci.engineer.report import assemble_report

def test_green_when_no_regression():
    r = assemble_report(candidate_label="benign-1", regression=False,
                        flips={"pass_to_fail": [], "fail_to_pass": []},
                        cluster=None, fix=None, promotion=None, mcp_calls=3)
    assert r["verdict"] == "green_no_regression"
    assert r["gate"] == "green"

def test_green_when_fix_promotable():
    r = assemble_report(candidate_label="reg-refund", regression=True,
                        flips={"pass_to_fail": ["t05"], "fail_to_pass": []},
                        cluster={"label": "refund-policy"},
                        fix={"revised_prompt": "p", "rationale": "r"},
                        promotion={"promotable": True, "lift": 0.2, "n": 16,
                                   "heldout_regressions": 0, "reason": "ok"},
                        mcp_calls=5)
    assert r["verdict"] == "green_promotable_fix"
    assert r["gate"] == "green"

def test_red_when_no_qualifying_fix():
    r = assemble_report(candidate_label="reg-hard", regression=True,
                        flips={"pass_to_fail": ["t09"], "fail_to_pass": []},
                        cluster={"label": "x"},
                        fix={"revised_prompt": "p", "rationale": "r"},
                        promotion={"promotable": False, "lift": 0.01, "n": 16,
                                   "heldout_regressions": 0, "reason": "insufficient"},
                        mcp_calls=5)
    assert r["verdict"] == "red_no_fix"
    assert r["gate"] == "red"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.report'`.

- [ ] **Step 3: Write `agentci/engineer/report.py`**

```python
"""Assemble the terminal run report consumed by the CLI and dashboard."""


def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls):
    """Build the run report. Encodes all terminal outcomes incl. no-fix->RED (GAP-6)."""
    if not regression:
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
        "mcp_calls": mcp_calls,         # evidences load-bearing MCP (GAP-4)
        "verdict": verdict,
        "gate": gate,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_report.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/report.py tests/test_report.py
git commit -m "feat: run report assembly incl. no-fix RED path (GAP-6)"
```

---

### Task 9: The orchestrated single-candidate run

**Files:**
- Modify: `agentci/engineer/__init__.py` (add `run_check`)
- Test: `tests/test_run_check.py`

`run_check(candidate_prompt, label)` wires the pieces: fetch baseline (tune+held-out) via MCP, run candidate on tune, detect regression. If green → report green. If regression → cluster, fix, run fixed on held-out, evaluate promotion, (if promotable) mint case, assemble report. We test the control flow with the LLM/MCP/experiment functions monkeypatched.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_check.py
from agentci import engineer

def _rows(split, ids, passed):
    return [{"id": i, "split": split, "passed": passed,
             "scores": {"correctness": 0.9 if passed else 0.2, "groundedness": 0.9,
                        "completeness": 0.9, "policy_reference": 0.9}} for i in ids]

def test_benign_candidate_returns_green(monkeypatch):
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], True))
    monkeypatch.setattr(engineer, "run_candidate",
                        lambda prompt, ds, split, name: _rows(split, ["t00"] if split=="tune" else ["h0"], True))
    monkeypatch.setattr(engineer, "_mcp_call_count", lambda: 2)
    report = engineer.run_check("BENIGN PROMPT", "benign-1")
    assert report["verdict"] == "green_no_regression"

def test_regressive_candidate_with_good_fix_promotes(monkeypatch):
    # baseline passes everywhere; candidate fails t00 (tune) -> regression
    def fake_run(prompt, ds, split, name):
        if "FIX" in prompt:                       # fixed prompt restores held-out
            return _rows(split, ["t00"] if split=="tune" else ["h0"], True)
        if split == "tune":
            return _rows("tune", ["t00"], False)  # candidate regresses tune
        return _rows("held_out", ["h0"], False)   # candidate also bad on held-out
    monkeypatch.setattr(engineer, "fetch_baseline_via_mcp",
                        lambda name: _rows("tune", ["t00"], True) + _rows("held_out", ["h0"], True))
    monkeypatch.setattr(engineer, "run_candidate", fake_run)
    monkeypatch.setattr(engineer, "cluster_failures",
                        lambda cases: {"label": "refund-policy", "policy_id": "refund-policy",
                                       "summary": "s", "case_ids": ["t00"]})
    monkeypatch.setattr(engineer, "draft_fix",
                        lambda p, c: {"revised_prompt": p + " FIX", "rationale": "r"})
    monkeypatch.setattr(engineer, "build_minted_case",
                        lambda cluster, question, gold, index=0: {"id": "minted-x", "split": "tune"})
    monkeypatch.setattr(engineer, "persist_minted_case", lambda case: None)
    monkeypatch.setattr(engineer, "_mcp_call_count", lambda: 4)
    report = engineer.run_check("SHORT PROMPT", "reg-refund")
    assert report["regression_detected"] is True
    assert report["verdict"] == "green_promotable_fix"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_check.py -v`
Expected: FAIL with `AttributeError: module 'agentci.engineer' has no attribute 'run_check'`.

- [ ] **Step 3: Write `run_check` into `agentci/engineer/__init__.py`**

```python
"""Engineer package: orchestrates one AgentCI check run."""
from agentci import config
from agentci.engineer.compare import fetch_baseline_via_mcp, compute_flips, is_regression
from agentci.engineer.cluster import cluster_failures
from agentci.engineer.fix import draft_fix
from agentci.engineer.mint import build_minted_case, persist_minted_case
from agentci.engineer.lift import evaluate_promotion
from agentci.engineer.report import assemble_report
from agentci.evals.experiment import run_candidate
from agentci.data.dataset import load_tickets

_MCP_CALLS = {"n": 0}


def _mcp_call_count() -> int:
    return _MCP_CALLS["n"]


def _split(rows, split):
    return [r for r in rows if r["split"] == split]


def _gold_for(cluster) -> tuple[str, str]:
    """Pick a representative question + gold from the cluster's first case id."""
    by_id = {t["id"]: t for t in load_tickets()}
    cid = (cluster.get("case_ids") or [None])[0]
    t = by_id.get(cid, {})
    return (t.get("question", f"Question about {cluster['label']}"),
            t.get("gold_resolution", cluster.get("summary", "")))


def run_check(candidate_prompt: str, label: str) -> dict:
    """Run one AgentCI check: detect -> (cluster -> fix -> held-out lift -> mint) -> report."""
    baseline = fetch_baseline_via_mcp("baseline-tune") + fetch_baseline_via_mcp("baseline-heldout")
    _MCP_CALLS["n"] = _mcp_call_count() or 0

    cand_tune = run_candidate(candidate_prompt, config.DATASET_NAME, "tune", f"cand-{label}-tune")
    flips = compute_flips(_split(baseline, "tune"), cand_tune)

    if not is_regression(_split(baseline, "tune"), cand_tune):
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count())

    failing = [{"id": cid} for cid in flips["pass_to_fail"]]
    by_id = {t["id"]: t for t in load_tickets()}
    cand_by_id = {r["id"]: r for r in cand_tune}
    cases = [{
        "id": cid,
        "question": by_id.get(cid, {}).get("question", ""),
        "gold": by_id.get(cid, {}).get("gold_resolution", ""),
        "answer": cand_by_id.get(cid, {}).get("answer", ""),  # present per Plan 02 row contract
    } for cid in flips["pass_to_fail"]]
    cluster = cluster_failures(cases)

    fix = draft_fix(candidate_prompt, cluster)
    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    promotion = evaluate_promotion(_split(baseline, "held_out"), fixed_heldout)

    if promotion["promotable"]:
        q, gold = _gold_for(cluster)
        persist_minted_case(build_minted_case(cluster, q, gold))

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count())
```

> Note: the `answer` field comes from the Plan 02 per-case row contract (`{"id","split","answer","scores","passed"}`). If, during execution, the experiment extraction does not populate `answer`, fall back to re-calling `answer_ticket(candidate_prompt, question)` here — but keep the `cases[*].answer` field populated either way.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_check.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/__init__.py tests/test_run_check.py
git commit -m "feat: orchestrated single-candidate check run"
```

---

### Task 10: The labeled battery candidates (D4)

**Files:**
- Create: `candidates/labels.json`
- Create: `candidates/reg_refund.txt`, `reg_routing.txt`, `benign_reword.txt`, `benign_format.txt`, `improve_cite.txt`, `improve_clarify.txt`
- Test: `tests/test_candidates.py`

Six candidates (D4): 2 regressive (incl. the headline refund-policy one), 2 benign, 2 improving. Each is a full system-prompt variant of `BASELINE_SUPPORT_PROMPT`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_candidates.py
import json
from pathlib import Path

CAND = Path("candidates")

def test_labels_cover_six_with_correct_split():
    labels = json.loads((CAND / "labels.json").read_text())
    assert len(labels) == 6
    counts = {}
    for v in labels.values():
        counts[v] = counts.get(v, 0) + 1
    assert counts == {"regressive": 2, "benign": 2, "improving": 2}  # D4

def test_every_candidate_file_exists_and_nonempty():
    labels = json.loads((CAND / "labels.json").read_text())
    for fname in labels:
        p = CAND / fname
        assert p.exists() and len(p.read_text().strip()) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_candidates.py -v`
Expected: FAIL with `FileNotFoundError` for `candidates/labels.json`.

- [ ] **Step 3: Write `candidates/labels.json`**

```json
{
  "reg_refund.txt": "regressive",
  "reg_routing.txt": "regressive",
  "benign_reword.txt": "benign",
  "benign_format.txt": "benign",
  "improve_cite.txt": "improving",
  "improve_clarify.txt": "improving"
}
```

- [ ] **Step 4: Write the six candidate prompt files**

`candidates/reg_refund.txt` (the headline: tightened to save tokens, silently drops refund detail):

```text
You are a SaaS billing support agent. Answer briefly using the lookup_kb tool. Keep answers short.
```

`candidates/reg_routing.txt` (drops the human-routing instruction):

```text
You are a customer-support agent for a SaaS billing product. Use only the knowledge base from
lookup_kb to answer, and cite the policy section you used. Always attempt to answer directly.
```

`candidates/benign_reword.txt` (same behavior, reworded):

```text
You are a support agent for a SaaS billing product. Answer using ONLY the knowledge base returned
by the lookup_kb tool, and always cite the exact policy section you relied on. If the knowledge base
does not cover the question, say you will route the ticket to a human and name the team. For refund
questions, explicitly state the refund window and any eligibility conditions.
```

`candidates/benign_format.txt` (same behavior, asks for bullet formatting):

```text
You are a customer-support agent for a SaaS billing product. Use ONLY the knowledge base returned by
the lookup_kb tool to answer, formatting the answer as short bullet points. Always cite the exact
policy section you relied on. If the knowledge base does not cover the question, say you will route
the ticket to a human and name the team. For refund questions, state the refund window and any
eligibility conditions explicitly.
```

`candidates/improve_cite.txt` (adds an explicit citation format — should help policy_reference):

```text
You are a customer-support agent for a SaaS billing product. Use ONLY the knowledge base returned by
the lookup_kb tool to answer. Always cite the exact policy section you relied on using the format
[policy: <section title>]. If the knowledge base does not cover the question, say you will route the
ticket to a human and name the team. For refund questions, state the refund window and any
eligibility conditions explicitly.
```

`candidates/improve_clarify.txt` (adds completeness checklist — should help completeness):

```text
You are a customer-support agent for a SaaS billing product. Use ONLY the knowledge base returned by
the lookup_kb tool to answer, and cite the exact policy section you relied on. Before finishing,
verify you have stated every condition the policy lists (windows, eligibility, timing). If the
knowledge base does not cover the question, say you will route the ticket to a human and name the
team. For refund questions, state the refund window and any eligibility conditions explicitly.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_candidates.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add candidates/ tests/test_candidates.py
git commit -m "feat: labeled 6-candidate battery (D4)"
```

---

### Task 11: Battery runner + confusion matrix (GAP-1/GAP-2)

**Files:**
- Create: `agentci/engineer/battery.py`
- Test: `tests/test_battery.py`

`build_confusion_matrix(results, labels)` scores detection: a candidate has `expected_regression = (label == "regressive")`; `predicted_regression = report["regression_detected"]`. Produces TP/FP/TN/FN counts. The GAP-2 guarantee is **FP == 0** (no benign/improving candidate flagged). `run_battery()` runs all six and returns `{reports, confusion}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_battery.py
from agentci.engineer.battery import build_confusion_matrix

def test_confusion_matrix_counts():
    reports = {
        "reg_refund.txt": {"regression_detected": True},
        "reg_routing.txt": {"regression_detected": True},
        "benign_reword.txt": {"regression_detected": False},
        "benign_format.txt": {"regression_detected": False},
        "improve_cite.txt": {"regression_detected": False},
        "improve_clarify.txt": {"regression_detected": False},
    }
    labels = {
        "reg_refund.txt": "regressive", "reg_routing.txt": "regressive",
        "benign_reword.txt": "benign", "benign_format.txt": "benign",
        "improve_cite.txt": "improving", "improve_clarify.txt": "improving",
    }
    cm = build_confusion_matrix(reports, labels)
    assert cm == {"tp": 2, "fp": 0, "tn": 4, "fn": 0, "false_positive_rate": 0.0}

def test_false_positive_is_counted():
    reports = {"benign_reword.txt": {"regression_detected": True}}
    labels = {"benign_reword.txt": "benign"}
    cm = build_confusion_matrix(reports, labels)
    assert cm["fp"] == 1 and cm["false_positive_rate"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_battery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.engineer.battery'`.

- [ ] **Step 3: Write `agentci/engineer/battery.py`**

```python
"""Run the labeled candidate battery and score detection (GAP-1 proof, GAP-2 FP guard)."""
import json
from pathlib import Path

from agentci.engineer import run_check

_CAND_DIR = Path("candidates")


def build_confusion_matrix(reports: dict, labels: dict) -> dict:
    """Score regression detection. expected_regression iff label=='regressive'."""
    tp = fp = tn = fn = 0
    for fname, report in reports.items():
        expected = labels[fname] == "regressive"
        predicted = bool(report["regression_detected"])
        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1
    negatives = tn + fp
    fpr = round(fp / negatives, 4) if negatives else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "false_positive_rate": fpr}


def run_battery() -> dict:
    """Run all six labeled candidates through run_check; return reports + confusion matrix."""
    labels = json.loads((_CAND_DIR / "labels.json").read_text(encoding="utf-8"))
    reports = {}
    for fname, label in labels.items():
        prompt = (_CAND_DIR / fname).read_text(encoding="utf-8").strip()
        reports[fname] = run_check(prompt, label)
    confusion = build_confusion_matrix(reports, labels)
    return {"reports": reports, "confusion": confusion}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_battery.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/engineer/battery.py tests/test_battery.py
git commit -m "feat: battery runner + confusion matrix (GAP-1/GAP-2)"
```

---

### Task 12: Manual live integration (records all battery fixtures)

- [ ] **Step 1: Produce the baseline held-out experiment** (tune baseline came from Plan 02)

Run: `uv run python -c "from agentci.tracing import init_tracing; from agentci.evals.experiment import run_candidate; from agentci import config; import os; os.environ['AGENTCI_CACHE_MODE']='record'; init_tracing(); run_candidate(config.BASELINE_SUPPORT_PROMPT, config.DATASET_NAME, 'held_out', 'baseline-heldout')"`
Expected: `baseline-heldout` experiment appears in Phoenix.

- [ ] **Step 2: Run the full battery live (records fixtures)**

Run: `uv run python -c "from agentci.tracing import init_tracing; import os; os.environ['AGENTCI_CACHE_MODE']='record'; init_tracing(); from agentci.engineer.battery import run_battery; import json; r=run_battery(); print(json.dumps(r['confusion'], indent=2))"`
Expected: `{"tp": 2, "fp": 0, ...}` — both regressive caught, **zero false positives** (GAP-2). At least the `reg_refund.txt` candidate yields a `green_promotable_fix`. If a regressive candidate yields `red_no_fix`, that is a valid honest outcome (GAP-6) — verify it is the harder one, not the headline refund case.

- [ ] **Step 3: Verify MCP was load-bearing**

In Phoenix, open the Engineer project's traces. Expected: MCP tool-call spans (phoenix-mcp) fetching the baseline experiment — confirming the comparison read through MCP, not memory (GAP-4).

- [ ] **Step 4: Commit fixtures**

```bash
git add .agentci_cache
git commit -m "test: record full battery fixtures for deterministic replay"
```

---

## Self-review (Plan 03)

- **Spec coverage:** Engineer agent ✓ (§4.A), MCP as runtime tool ✓ (D1, GAP-4 via `fetch_baseline_via_mcp` + trace evidence), compare/cluster/fix/mint/lift ✓ (§5.4–5.6), held-out lift gate ✓ (D8/GAP-3), benign false-positive guard ✓ (GAP-2, FP==0 assertion), battery ✓ (D4/GAP-1), no-fix RED ✓ (GAP-6), determinism ✓ (cache).
- **Placeholder scan:** none. Three verify-and-adjust notes (ADK final-event predicate reused from Plan 01; client append method; `cases[*].answer` population) are real API-confirmation steps with pinned contracts.
- **Type consistency:** per-case row `{"id","split","passed","scores":{dim}}` consistent with Plan 02; `compute_flips` reused by `lift`; report keys (`verdict`,`gate`,`regression_detected`,`flips`,`cluster`,`proposed_fix`,`promotion`,`mcp_calls`) are the exact contract Plan 04 renders.

**Done when:** all pytest tests green AND the live battery shows `tp=2, fp=0`, the headline refund candidate produces a promotable fix with a minted case, and MCP tool-call spans are visible in the Engineer's Phoenix traces.
