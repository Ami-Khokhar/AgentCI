# Quality Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, self-improving Quality Memory layer to AgentCI — the investigator reads relevant past failures before diagnosing, entries are written only on human approval, and the dashboard shows a memory timeline.

**Architecture:** A new pure-Python `agentci/memory/` module backed by a git-tracked `quality_memory.json`. `run_check` reads relevant entries (matched by the flipped cases' `policy_id`) and feeds them into the agentic `diagnose()` call. The single human-approval path (`POST /api/approve` and a new `agentci approve` CLI) writes one entry via a new `record_approval()` function. The report gains two additive keys (`prior_knowledge`, `memory_entry`); the dashboard renders a timeline and a "prior knowledge applied" callout. Determinism is preserved: matched lessons join the `diagnose` cache payload **only when non-empty**, so existing replay fixtures stay valid, and tests isolate memory via `AGENTCI_MEMORY_PATH`.

**Tech Stack:** Python 3.13/3.14 (`uv`), pytest, Click (CLI), FastAPI (dashboard), the repo's `agentci/cache.py` record/replay pattern.

---

## Frozen-decision note (read first)

This plan **amends decision D11** (the investigator was "stateless"; it now reads Quality Memory before diagnosing). Task 5 records this amendment in the decision table at `docs/superpowers/plans/2026-06-01-agentci-00-overview.md` — per the repo rule, the table is updated, not silently deviated from. No other frozen decision changes. Existing verdict strings are **not** renamed (D8/D10/D16 consumers depend on them).

## File Structure

- **Create** `agentci/memory/__init__.py` — package marker, re-exports the public functions.
- **Create** `agentci/memory/memory.py` — pure functions: `load_memory`, `append_entry`, `find_relevant`, `format_for_prompt`, `build_entry`, `record_approval`. No LLM/network.
- **Create** `agentci/memory/quality_memory.json` — git-tracked store, seeded as `[]`.
- **Modify** `agentci/engineer/diagnose.py` — `diagnose()` gains a `prior_lessons` param (prompt injection + conditional cache-payload).
- **Modify** `agentci/engineer/report.py` — `assemble_report()` gains a `prior_knowledge` param.
- **Modify** `agentci/engineer/__init__.py` — `run_check()` reads memory and passes it through.
- **Modify** `agentci/server/app.py` — approve route writes a memory entry; new `GET /api/memory`.
- **Modify** `agentci/cli.py` — new `agentci approve` command.
- **Modify** `agentci/server/static/index.html` — memory timeline panel + "prior knowledge applied" callout.
- **Create** `tests/test_memory.py`, `tests/test_cli_approve.py` — new tests.
- **Modify** `tests/test_diagnose.py`, `tests/test_run_check.py`, `tests/test_report.py`, `tests/test_server.py` — extend for new behavior + isolate `AGENTCI_MEMORY_PATH`.
- **Modify** docs (Task 5): overview decision table, `docs/system-diagram.md`, `agentci-build-log.html`, `README.md`; **Create** `candidates/reg_concise.txt`.

## Execution method (worktrees + Sonnet subagents)

Foundation-first because `report.py` / `run_check` are shared. Each task is built by a Sonnet subagent in its own git worktree off `main`, then merged `--no-ff`:

- **Task 1** (branch `qm/01-memory-module`) — foundation; **blocks 2–4**.
- **Tasks 2, 3, 4** (branches `qm/02-read-path`, `qm/03-write-path`, `qm/04-dashboard`) — fan out after Task 1 merges.
- **Task 5** (branch `qm/05-docs-demo`) — lands last.

Run `uv run pytest -q` from the repo root after every task; the full suite must stay green.

---

### Task 1: Quality Memory module

**Files:**
- Create: `agentci/memory/__init__.py`
- Create: `agentci/memory/memory.py`
- Create: `agentci/memory/quality_memory.json`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Create the seed store**

Create `agentci/memory/quality_memory.json` with exactly:

```json
[]
```

- [ ] **Step 2: Create the package marker**

Create `agentci/memory/__init__.py`:

```python
"""Quality Memory: the self-improving institutional-memory layer (read on diagnose, write on approval)."""
from agentci.memory.memory import (  # noqa: F401
    append_entry,
    build_entry,
    find_relevant,
    format_for_prompt,
    load_memory,
    record_approval,
)
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_memory.py`:

```python
import json

import pytest

from agentci.memory import memory


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))


def test_load_empty_when_missing():
    assert memory.load_memory() == []


def test_append_round_trip():
    memory.append_entry({"failure_type": "factual_omission", "lesson": "L"})
    memory.append_entry({"failure_type": "over_refusal", "lesson": "M"})
    out = memory.load_memory()
    assert [e["lesson"] for e in out] == ["L", "M"]


def test_find_relevant_matches_by_policy(monkeypatch):
    # t-refund maps to policy 'refund-policy' via the frozen ticket suite.
    monkeypatch.setattr(memory, "_policy_by_case",
                        lambda: {"t-refund": "refund-policy", "t-other": "login"})
    memory.append_entry({"failure_type": "factual_omission", "lesson": "concise drops citations",
                         "affected_policies": ["refund-policy"]})
    memory.append_entry({"failure_type": "format_regression", "lesson": "unrelated",
                         "affected_policies": ["billing"]})
    hits = memory.find_relevant(["t-refund"])
    assert len(hits) == 1 and hits[0]["lesson"] == "concise drops citations"


def test_find_relevant_empty_for_no_flips():
    assert memory.find_relevant([]) == []


def test_format_for_prompt_empty_is_blank():
    assert memory.format_for_prompt([]) == ""


def test_format_for_prompt_renders_lessons():
    txt = memory.format_for_prompt([{"failure_type": "factual_omission",
                                     "lesson": "concise drops citations",
                                     "successful_fix": "force citation"}])
    assert "factual_omission" in txt and "concise drops citations" in txt


def test_build_entry_maps_report_fields(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case", lambda: {"t05": "refund-policy"})
    report = {
        "candidate_label": "reg-concise",
        "flips": {"pass_to_fail": ["t05"], "fail_to_pass": []},
        "investigation": {"root_cause": {"category": "factual_omission", "policy_id": "refund-policy",
                                          "summary": "dropped the 14-day window"}},
        "proposed_fix": {"rationale": "always cite refund policy"},
        "proposed_mint": {"id": "minted-refund-policy-0",
                          "guard": '{"slug": "refund-window"}'},
    }
    e = memory.build_entry(report, timestamp="2026-06-08T00:00:00+00:00")
    assert e["failure_type"] == "factual_omission"
    assert e["triggering_prompt_change"] == "reg-concise"
    assert e["root_cause"] == "dropped the 14-day window"
    assert e["affected_cases"] == ["t05"]
    assert e["affected_policies"] == ["refund-policy"]
    assert e["successful_fix"] == "always cite refund policy"
    assert e["failed_fixes"] == []
    assert e["new_eval_cases"] == {"id": "minted-refund-policy-0", "guard_slug": "refund-window"}
    assert e["approval_status"] == "approved"
    assert e["timestamp"] == "2026-06-08T00:00:00+00:00"
    assert "citation" in e["lesson"].lower() or "detail" in e["lesson"].lower()


def test_record_approval_appends_and_returns(monkeypatch):
    monkeypatch.setattr(memory, "_policy_by_case", lambda: {"t05": "refund-policy"})
    report = {"candidate_label": "reg-concise",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "r"},
              "proposed_mint": {"id": "minted-0", "guard": "{}"}}
    entry = memory.record_approval(report, timestamp="2026-06-08T00:00:00+00:00")
    assert entry["failure_type"] == "factual_omission"
    assert memory.load_memory() == [entry]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_memory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentci.memory'` (or attribute errors).

- [ ] **Step 5: Implement `memory.py`**

Create `agentci/memory/memory.py`:

```python
"""Quality Memory (self-improving layer): a persistent, git-tracked archive of past regressions.

The investigator READS relevant entries before diagnosing (D11 amendment, 2026-06-08); entries are
WRITTEN only on human approval (D12). Pure functions — no LLM calls, no network."""
import json
import os
from pathlib import Path

from agentci.data.dataset import load_tickets

_DEFAULT_PATH = Path(__file__).resolve().parent / "quality_memory.json"

# Deterministic, templated lessons keyed by the diagnosis taxonomy (config.FAILURE_TAXONOMY).
# No LLM call — the surfaced "pattern" is a stable string the investigator can reuse.
_LESSON_TEMPLATES = {
    "factual_omission": "Making prompts more concise often removes required citation/policy detail "
                        "from answers.",
    "over_refusal": "Cautious or restrictive wording can make the agent over-refuse tickets the "
                    "knowledge base actually covers.",
    "policy_miscite": "Loosening citation instructions can cause the agent to cite the wrong policy.",
    "hallucination": "Removing grounding constraints invites fabricated answers.",
    "format_regression": "Changing tone/format instructions can break required output structure.",
}

_CATEGORY_DIM = {
    "factual_omission": "completeness/correctness",
    "over_refusal": "correctness",
    "policy_miscite": "policy_reference",
    "hallucination": "groundedness",
    "format_regression": "completeness",
}


def _path() -> Path:
    return Path(os.environ.get("AGENTCI_MEMORY_PATH", str(_DEFAULT_PATH)))


def load_memory() -> list[dict]:
    """Return all entries (oldest first). Empty list if the store does not exist."""
    p = _path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def append_entry(entry: dict) -> None:
    """Append one entry to the store, creating it if needed."""
    entries = load_memory()
    entries.append(entry)
    _path().write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _policy_by_case() -> dict:
    """Map every frozen ticket id to its policy_id (the cross-failure matching key)."""
    return {t["id"]: t["policy_id"] for t in load_tickets()}


def _policies_for(case_ids: list[str], policy_by_case: dict) -> set:
    return {policy_by_case[c] for c in case_ids if c in policy_by_case}


def find_relevant(flipped_case_ids: list[str]) -> list[dict]:
    """Past entries whose affected policies intersect the flipped cases' policies.

    Policy id is the matching key because it is available BEFORE diagnosis runs.
    """
    if not flipped_case_ids:
        return []
    flipped_policies = _policies_for(flipped_case_ids, _policy_by_case())
    if not flipped_policies:
        return []
    return [e for e in load_memory()
            if set(e.get("affected_policies") or []) & flipped_policies]


def format_for_prompt(entries: list[dict]) -> str:
    """Render matched lessons for injection into the diagnose prompt. Stable + deterministic.

    Returns "" for the empty case so an empty memory does not perturb the cache key.
    """
    if not entries:
        return ""
    lines = [f"- [{e.get('failure_type', '?')}] {e.get('lesson', '')} "
             f"(past fix: {e.get('successful_fix', '')})" for e in entries]
    return "Prior lessons from past regressions (apply if relevant):\n" + "\n".join(lines)


def _lesson(failure_type: str) -> str:
    return _LESSON_TEMPLATES.get(failure_type, "A prompt change reintroduced a known failure mode.")


def build_entry(report: dict, timestamp: str) -> dict:
    """Construct one Quality Memory entry from an approved run report."""
    inv = report.get("investigation") or {}
    rc = inv.get("root_cause") or {}
    fix = report.get("proposed_fix") or {}
    flips = report.get("flips") or {}
    mint = report.get("proposed_mint") or {}

    affected = list(flips.get("pass_to_fail") or [])
    policies = _policies_for(affected, _policy_by_case())
    if rc.get("policy_id"):
        policies.add(rc["policy_id"])
    failure_type = rc.get("category") or "unknown"

    try:
        guard_slug = json.loads(mint.get("guard") or "{}").get("slug")
    except (ValueError, TypeError):
        guard_slug = None

    return {
        "failure_type": failure_type,
        "triggering_prompt_change": report.get("candidate_label"),
        "root_cause": rc.get("summary"),
        "lesson": _lesson(failure_type),
        "successful_fix": fix.get("rationale"),
        "failed_fixes": [],
        "affected_cases": affected,
        "affected_policies": sorted(p for p in policies if p),
        "evaluator_notes": f"{_CATEGORY_DIM.get(failure_type, 'correctness')} regressed on "
                           f"{len(affected)} case(s).",
        "new_eval_cases": {"id": mint.get("id"), "guard_slug": guard_slug},
        "approval_status": "approved",
        "timestamp": timestamp,
    }


def record_approval(report: dict, timestamp: str) -> dict:
    """Build + append a memory entry for an approved run. The ONLY write path (human-gated, D12)."""
    entry = build_entry(report, timestamp)
    append_entry(entry)
    return entry
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_memory.py -q`
Expected: PASS (8 tests).

- [ ] **Step 7: Confirm the full suite is still green**

Run: `uv run pytest -q`
Expected: PASS — no existing test touched yet.

- [ ] **Step 8: Commit**

```bash
git add agentci/memory/ tests/test_memory.py
git commit -m "feat(memory): Quality Memory store + pure helpers (read/write/match)"
```

---

### Task 2: Read path — investigator reads memory (amends D11)

**Files:**
- Modify: `agentci/engineer/diagnose.py:74-87`
- Modify: `agentci/engineer/diagnose.py:10-37` (goal template)
- Modify: `agentci/engineer/report.py:4-33`
- Modify: `agentci/engineer/__init__.py:51-130`
- Test: `tests/test_diagnose.py`, `tests/test_report.py`, `tests/test_run_check.py`

- [ ] **Step 1: Write the failing diagnose test (empty memory ⇒ identical cache key)**

Append to `tests/test_diagnose.py`:

```python
def test_diagnose_empty_lessons_keeps_legacy_cache_key(tmp_path, monkeypatch):
    # With no prior lessons, the cache payload (and key) must be byte-identical to the
    # pre-memory key, so existing recordings keep replaying.
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"]}
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(
        json.dumps({"root_cause": {"category": "factual_omission"}, "guard": {"kind": "assertion"},
                    "mcp_calls": 1}))
    out = diagnose("P", "reg-refund", ["t00"], prior_lessons=[])
    assert out["root_cause"]["category"] == "factual_omission"


def test_diagnose_nonempty_lessons_changes_cache_key(tmp_path, monkeypatch):
    # A non-empty lesson set must alter the payload so the recording is honest.
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    lessons = [{"failure_type": "factual_omission", "lesson": "concise drops citations"}]
    payload = {"candidate_prompt": "P", "label": "reg-refund", "pass_to_fail": ["t00"],
               "prior_lessons": [{"failure_type": "factual_omission", "lesson": "concise drops citations"}]}
    (tmp_path / (cache._key("diagnosis", payload) + ".json")).write_text(
        json.dumps({"root_cause": {"category": "factual_omission"}, "guard": {"kind": "assertion"},
                    "mcp_calls": 2}))
    out = diagnose("P", "reg-refund", ["t00"], prior_lessons=lessons)
    assert out["mcp_calls"] == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_diagnose.py -q`
Expected: FAIL — `diagnose() got an unexpected keyword argument 'prior_lessons'`.

- [ ] **Step 3: Add `prior_lessons` to `diagnose()`**

In `agentci/engineer/diagnose.py`, add the import near the top (after line 8 `from agentci import cache, config`):

```python
from agentci.memory import memory
```

Add a placeholder to the goal template. Change line 10's opening of `_DIAGNOSIS_GOAL` so the block sits right after the flipped-cases line. Replace:

```python
_DIAGNOSIS_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped PASS->FAIL versus baseline: {pass_to_fail}.

Investigate WHY, like a reliability engineer.
```

with:

```python
_DIAGNOSIS_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped PASS->FAIL versus baseline: {pass_to_fail}.
{prior_lessons_block}
Investigate WHY, like a reliability engineer.
```

In `_run_diagnosis`, change the signature and the `.format(...)` call. Replace the signature line:

```python
async def _run_diagnosis(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> tuple[str, int]:
```

with:

```python
async def _run_diagnosis(candidate_prompt: str, label: str, pass_to_fail: list[str],
                         prior_lessons_block: str = "") -> tuple[str, int]:
```

and replace the `goal = _DIAGNOSIS_GOAL.format(` call (lines 54-60) by adding the new field:

```python
    goal = _DIAGNOSIS_GOAL.format(
        label=label, pass_to_fail=pass_to_fail,
        taxonomy=", ".join(config.FAILURE_TAXONOMY),
        candidate_prompt=candidate_prompt,
        cand_experiment_id=experiments_registry.get_id(f"cand-{label}-tune"),
        baseline_experiment_id=experiments_registry.get_id("baseline-tune"),
        prior_lessons_block=("\n" + prior_lessons_block + "\n") if prior_lessons_block else "",
    )
```

Replace the whole `diagnose(...)` function (lines 74-87) with:

```python
def diagnose(candidate_prompt: str, label: str, pass_to_fail: list[str],
             prior_lessons: list[dict] | None = None) -> dict:
    """Root cause + taxonomy + headline + authored guard. No fix (D19). Cached (D7).

    `prior_lessons` (Quality Memory hits, D11 amendment 2026-06-08) are injected into the prompt and
    join the cache payload ONLY when non-empty, so an empty memory replays the legacy key unchanged.
    """
    prior_lessons = prior_lessons or []
    payload = {"candidate_prompt": candidate_prompt, "label": label, "pass_to_fail": sorted(pass_to_fail)}
    if prior_lessons:
        payload["prior_lessons"] = [{"failure_type": e.get("failure_type"), "lesson": e.get("lesson")}
                                    for e in prior_lessons]
    block = memory.format_for_prompt(prior_lessons)

    def live():
        from agentci import throttle
        raw, mcp_calls = throttle.call_with_backoff(
            lambda: asyncio.run(_run_diagnosis(candidate_prompt, label, pass_to_fail, block))
        )
        data = _parse_json(raw)
        data["mcp_calls"] = mcp_calls
        return data

    return cache.cached("diagnosis", payload, live)
```

- [ ] **Step 4: Run diagnose tests to verify pass**

Run: `uv run pytest tests/test_diagnose.py -q`
Expected: PASS (all, including the two new tests and the pre-existing `test_diagnose_replays_with_guard_and_taxonomy`, which uses the legacy payload).

- [ ] **Step 5: Write the failing report test**

Append to `tests/test_report.py`:

```python
def test_report_carries_prior_knowledge():
    from agentci.engineer.report import assemble_report
    hits = [{"failure_type": "factual_omission", "lesson": "concise drops citations"}]
    rep = assemble_report("reg-concise", True, {"pass_to_fail": ["t05"], "fail_to_pass": []},
                          None, None, None, 3, prior_knowledge=hits)
    assert rep["prior_knowledge"] == hits


def test_report_prior_knowledge_defaults_empty():
    from agentci.engineer.report import assemble_report
    rep = assemble_report("safe", False, {"pass_to_fail": [], "fail_to_pass": []},
                          None, None, None, 2)
    assert rep["prior_knowledge"] == []
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_report.py -q`
Expected: FAIL — `assemble_report() got an unexpected keyword argument 'prior_knowledge'`.

- [ ] **Step 7: Add `prior_knowledge` to `assemble_report()`**

In `agentci/engineer/report.py`, change the signature (line 4-6) by appending `prior_knowledge=None`:

```python
def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls,
                    investigation=None, proposed_mint=None, guard_gate=None,
                    proposed_guard=None, guard_review=None, meta_metrics=None,
                    prior_knowledge=None):
```

and add this key to the returned dict (insert right after the `"meta_metrics": meta_metrics,` line):

```python
        "prior_knowledge": prior_knowledge or [],   # NEW: Quality Memory entries the investigator read (D11 amendment)
```

- [ ] **Step 8: Run report tests to verify pass**

Run: `uv run pytest tests/test_report.py -q`
Expected: PASS.

- [ ] **Step 9: Wire `run_check` to read memory and pass it through**

In `agentci/engineer/__init__.py`, add the import after line 12 (`from agentci.engineer.review import ...`):

```python
from agentci.memory import memory
```

In `run_check`, immediately after the flips line (`flips = compute_flips(...)`, line 66) add:

```python
    prior_knowledge = memory.find_relevant(flips["pass_to_fail"])
```

Pass `prior_lessons` into the diagnose call (replace line 84):

```python
    diagnosis = diagnose(candidate_prompt, label, flips["pass_to_fail"], prior_lessons=prior_knowledge)
```

Pass `prior_knowledge` into the **final** `assemble_report` (the regression-path return, lines 127-130). Replace it with:

```python
    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count(),
                           investigation=diagnosis, proposed_mint=proposed_mint,
                           guard_gate=guard_gate, proposed_guard=proposed_guard,
                           guard_review=guard_review, meta_metrics=meta,
                           prior_knowledge=prior_knowledge)
```

(The two early returns — guard-blocked and no-regression — keep the default `prior_knowledge=[]`; no diagnosis happened.)

- [ ] **Step 10: Fix the monkeypatched `diagnose` signature in run_check tests**

`run_check` now calls `diagnose(..., prior_lessons=prior_knowledge)`. `tests/test_run_check.py` monkeypatches `engineer.diagnose` with a 3-positional-arg lambda (in `test_regression_with_admitted_guard_and_good_fix`, line ~49) — that will raise `TypeError: <lambda>() got an unexpected keyword argument 'prior_lessons'`. Update every monkeypatched `diagnose` lambda to accept the new keyword. Change:

```python
    monkeypatch.setattr(engineer, "diagnose", lambda prompt, label, ptf: {
```

to:

```python
    monkeypatch.setattr(engineer, "diagnose", lambda prompt, label, ptf, prior_lessons=None: {
```

(The seed `quality_memory.json` ships as `[]`, so `memory.find_relevant` returns `[]` and `prior_knowledge` is empty in these tests — no `AGENTCI_MEMORY_PATH` override is strictly required here. Still, add `monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))` defensively to any run_check test that has `tmp_path`/`monkeypatch` available, so a populated demo store can never leak into these tests later.)

- [ ] **Step 11: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS. If a `cand-*`/`diagnosis` replay miss appears, a run_check test is reading a non-empty memory — fix its `AGENTCI_MEMORY_PATH` override (Step 10).

- [ ] **Step 12: Commit**

```bash
git add agentci/engineer/diagnose.py agentci/engineer/report.py agentci/engineer/__init__.py \
        tests/test_diagnose.py tests/test_report.py tests/test_run_check.py
git commit -m "feat(memory): investigator reads Quality Memory before diagnosing (amends D11)"
```

---

### Task 3: Write path — record on approval + `agentci approve` CLI

**Files:**
- Modify: `agentci/server/app.py:32-40`
- Modify: `agentci/cli.py`
- Test: `tests/test_server.py`, `tests/test_cli_approve.py`

- [ ] **Step 1: Write the failing server test (approve writes a memory entry)**

Append to `tests/test_server.py` (match the file's existing TestClient setup; if it builds the app via `create_app()`, reuse that). Add:

```python
def test_approve_writes_memory_entry(tmp_path, monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from agentci.server import app as appmod
    from agentci.engineer import mint

    monkeypatch.setattr(appmod, "_RUNS_DIR", tmp_path)
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    monkeypatch.setattr(mint, "approve_and_mint", lambda rep, ds=None: rep["proposed_mint"])

    report = {"candidate_label": "reg-concise", "gate": "green",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "always cite refund policy"},
              "proposed_mint": {"id": "minted-refund-policy-0", "guard": '{"slug": "refund-window"}'}}
    (tmp_path / "reg-concise.json").write_text(json.dumps(report))

    client = TestClient(appmod.create_app())
    r = client.post("/api/approve/reg-concise")
    assert r.status_code == 200
    body = r.json()
    assert body["memory_entry"]["failure_type"] == "factual_omission"

    persisted = json.loads((tmp_path / "reg-concise.json").read_text())
    assert persisted["memory_entry"]["failure_type"] == "factual_omission"

    from agentci.memory import memory
    assert len(memory.load_memory()) == 1


def test_get_memory_endpoint_returns_newest_first(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from agentci.server import app as appmod
    from agentci.memory import memory

    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    memory.append_entry({"failure_type": "a", "lesson": "first"})
    memory.append_entry({"failure_type": "b", "lesson": "second"})

    client = TestClient(appmod.create_app())
    out = client.get("/api/memory").json()
    assert [e["lesson"] for e in out] == ["second", "first"]
```

> Note: `_RUNS_DIR` is a module-level constant in `app.py`. The approve route reads it via the module global, so `monkeypatch.setattr(appmod, "_RUNS_DIR", tmp_path)` redirects both the report load and the write. If the existing `test_server.py` already has a working pattern for pointing the app at a temp runs dir, mirror that instead.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL — `KeyError: 'memory_entry'` and 404 on `/api/memory`.

- [ ] **Step 3: Update the approve route + add `/api/memory`**

In `agentci/server/app.py`, add imports after line 8 (`from agentci.engineer.mint import approve_and_mint`):

```python
from datetime import datetime, timezone

from agentci.memory import memory
```

Replace the approve route (lines 32-40) with:

```python
    @app.post("/api/approve/{label}")
    def approve(label: str):
        report = _load_report(label)
        if report.get("gate") != "green" or not report.get("proposed_mint"):
            raise HTTPException(status_code=409, detail="nothing to approve (gate not green / no proposed mint)")
        minted = approve_and_mint(report)
        entry = memory.record_approval(report, datetime.now(timezone.utc).isoformat())
        report["minted"] = minted
        report["memory_entry"] = entry
        (_RUNS_DIR / f"{label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"approved": True, "minted": minted, "memory_entry": entry}

    @app.get("/api/memory")
    def get_memory():
        return list(reversed(memory.load_memory()))
```

- [ ] **Step 4: Run server tests to verify pass**

Run: `uv run pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI approve test**

Create `tests/test_cli_approve.py`:

```python
import json

from click.testing import CliRunner

from agentci.cli import cli


def test_approve_command_mints_and_records(tmp_path, monkeypatch):
    from agentci.engineer import mint
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    monkeypatch.setattr(mint, "approve_and_mint", lambda rep, ds=None: rep["proposed_mint"])

    report = {"candidate_label": "reg-concise", "gate": "green",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "always cite refund policy"},
              "proposed_mint": {"id": "minted-refund-policy-0", "guard": '{"slug": "refund-window"}'}}
    run_path = tmp_path / "reg-concise.json"
    run_path.write_text(json.dumps(report))

    result = CliRunner().invoke(cli, ["approve", "--run", str(run_path)])
    assert result.exit_code == 0, result.output
    assert "minted-refund-policy-0" in result.output

    persisted = json.loads(run_path.read_text())
    assert persisted["memory_entry"]["failure_type"] == "factual_omission"

    from agentci.memory import memory
    assert len(memory.load_memory()) == 1


def test_approve_command_rejects_non_green(tmp_path):
    report = {"candidate_label": "reg", "gate": "red", "proposed_mint": None}
    run_path = tmp_path / "reg.json"
    run_path.write_text(json.dumps(report))
    result = CliRunner().invoke(cli, ["approve", "--run", str(run_path)])
    assert result.exit_code != 0
    assert "nothing to approve" in result.output
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_cli_approve.py -q`
Expected: FAIL — no `approve` command on the CLI group.

- [ ] **Step 7: Add the `agentci approve` command**

In `agentci/cli.py`, add this command at the end of the file (after the `check` command). It shares the exact mint path the API uses (`approve_and_mint`) plus `record_approval`:

```python
@cli.command()
@click.option("--run", "run_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Path to a run report JSON to approve.")
def approve(run_path):
    """Approve a green_promotable_fix run: promote the fix, mint the case, write Quality Memory (D12)."""
    from datetime import datetime, timezone

    from agentci.engineer.mint import approve_and_mint
    from agentci.memory import memory

    path = Path(run_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("gate") != "green" or not report.get("proposed_mint"):
        raise click.ClickException("nothing to approve (gate not green / no proposed mint)")

    minted = approve_and_mint(report)
    entry = memory.record_approval(report, datetime.now(timezone.utc).isoformat())
    report["minted"] = minted
    report["memory_entry"] = entry
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    click.echo(f"approved : {report.get('candidate_label')}")
    click.echo(f"minted   : {minted['id'] if minted else '—'}")
    click.echo(f"memory   : {entry['failure_type']} — {entry['lesson']}")
```

- [ ] **Step 8: Run CLI tests to verify pass**

Run: `uv run pytest tests/test_cli_approve.py -q`
Expected: PASS (2 tests).

- [ ] **Step 9: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add agentci/server/app.py agentci/cli.py tests/test_server.py tests/test_cli_approve.py
git commit -m "feat(memory): write Quality Memory on approval (API + agentci approve CLI)"
```

---

### Task 4: Dashboard — memory timeline + "prior knowledge applied"

**Files:**
- Modify: `agentci/server/static/index.html`

This task is UI-only (no pytest). Verify by booting the server and eyeballing.

- [ ] **Step 1: Add the "prior knowledge applied" callout in the investigation section**

In `agentci/server/static/index.html`, inside `render(rep)`, in section "2 — the catch", after the closing `</div>` of the investigation panel (i.e., right after the `<div class="rootcause">…</div>` line and before `</div></section>`), inject a callout when memory was applied. Locate the block (lines ~250-254) ending with:

```javascript
        <div class="rootcause"><b>Root cause —</b> ${esc(inv.root_cause?.summary)||"—"} <span style="color:var(--muted)">(policy: ${esc(inv.root_cause?.policy_id)||"?"}, cases: ${(inv.root_cause?.case_ids||[]).map(esc).join(", ")||"—"})</span></div>
      </div></section><div class="divider"></div>`;
```

Replace it with (adds a prior-knowledge line inside the panel):

```javascript
        <div class="rootcause"><b>Root cause —</b> ${esc(inv.root_cause?.summary)||"—"} <span style="color:var(--muted)">(policy: ${esc(inv.root_cause?.policy_id)||"?"}, cases: ${(inv.root_cause?.case_ids||[]).map(esc).join(", ")||"—"})</span></div>
        ${(rep.prior_knowledge&&rep.prior_knowledge.length)?`<div class="priorknow"><b>↺ Prior knowledge applied:</b> ${rep.prior_knowledge.map(e=>esc(e.lesson)).join(" · ")}</div>`:""}
      </div></section><div class="divider"></div>`;
```

- [ ] **Step 2: Add a small style for the callout**

In the `<style>` block, near the `.panel` rule (line ~65), add:

```css
  .priorknow{margin-top:10px;padding:8px 10px;border-left:3px solid var(--ok,#2e7d32);background:rgba(46,125,50,.08);font-size:13px}
  .qm-row{border:1px solid var(--hair);border-radius:4px;padding:10px 12px;margin-top:8px}
  .qm-row .qm-h{font-size:12px;color:var(--muted);display:flex;gap:10px;justify-content:space-between}
  .qm-row .qm-lesson{margin-top:4px}
```

- [ ] **Step 3: Add the Quality Memory timeline renderer + fetch**

In the `<script>`, add this function (place it right before `function render(rep){`):

```javascript
async function renderMemoryTimeline(){
  let entries = [];
  try{ entries = await fetch("/api/memory").then(r=>r.json()); }catch{ return; }
  if(!entries.length) return;
  const rows = entries.map(e=>`<div class="qm-row">
      <div class="qm-h"><span><b>${esc(e.failure_type)}</b> · ${esc(e.triggering_prompt_change)||"—"}</span>
        <span>${esc((e.timestamp||"").slice(0,10))}</span></div>
      <div class="qm-lesson">${esc(e.lesson)}</div>
      <div class="qm-h" style="margin-top:4px">fix: ${esc(e.successful_fix)||"—"} · cases: ${(e.affected_cases||[]).map(esc).join(", ")||"—"}</div>
    </div>`).join("");
  const h = `<div class="divider"></div><section><div class="step-label"><span class="n">⊕</span> Quality Memory</div>
    <h2>Every approved fix becomes institutional memory.</h2>
    <div class="sub">Each entry is read by future investigations. The loop compounds: regression → diagnosis → fix → memory → faster next time.</div>
    ${rows}</section>`;
  document.getElementById("content").insertAdjacentHTML("beforeend", h);
}
```

- [ ] **Step 4: Call the timeline after the report renders**

In `boot()`, change the final `render(await resp.json());` line to:

```javascript
  render(await resp.json());
  await renderMemoryTimeline();
```

- [ ] **Step 5: Verify in the browser**

```bash
uv run uvicorn agentci.server.app:app --port 8000 &
sleep 2
curl -s http://127.0.0.1:8000/api/memory
```

Expected: `curl` returns a JSON array (`[]` if no approvals yet, or entries newest-first). Open `http://127.0.0.1:8000/?run=<a run label>` and confirm: (a) the "Quality Memory" section renders at the bottom when entries exist, (b) the "Prior knowledge applied" callout shows in section 2 when a run's `prior_knowledge` is non-empty. Stop the server (`kill %1`).

- [ ] **Step 6: Commit**

```bash
git add agentci/server/static/index.html
git commit -m "feat(memory): dashboard Quality Memory timeline + prior-knowledge callout"
```

---

### Task 5: Docs + demo (lands last)

**Files:**
- Modify: `docs/superpowers/plans/2026-06-01-agentci-00-overview.md` (decision table)
- Create: `candidates/reg_concise.txt`
- Modify: `docs/system-diagram.md`
- Modify: `agentci-build-log.html`
- Modify: `README.md`

- [ ] **Step 1: Record the D11 amendment in the decision table**

In `docs/superpowers/plans/2026-06-01-agentci-00-overview.md`, in the D11 row (line ~27), append to the end of the cell text (before the closing `|`):

```
 **Amended 2026-06-08 (Quality Memory):** the investigator is no longer stateless — before diagnosing it reads relevant past failures from Quality Memory (matched by the flipped cases' `policy_id`) and folds them into its prompt. Matched lessons join the diagnose cache payload only when non-empty, preserving replay determinism for runs with empty memory.
```

- [ ] **Step 2: Add a D20 row for Quality Memory**

In the same table, after the D19 row (line ~35), add:

```
| D20 | **Quality Memory (self-improving layer)** | A git-tracked `agentci/memory/quality_memory.json` archives every approved regression (failure_type, root_cause, lesson, successful_fix, affected_cases/policies, minted case, timestamp). The investigator READS relevant entries before diagnosing (amends D11); entries are WRITTEN only on human approval (D12) via `record_approval` — the single write path, reached by `POST /api/approve` and `agentci approve`. Reject writes nothing. Storage is JSON for diffability and deterministic replay; tests isolate it via `AGENTCI_MEMORY_PATH`. |
```

- [ ] **Step 3: Create the second demo candidate**

Create `candidates/reg_concise.txt` — a prompt that triggers a *citation-suppression* regression in the same family as the headline refund case (so run #2's investigator matches the prior lesson):

```
You are a customer-support agent for a SaaS billing product.
Use ONLY the knowledge base returned by the `lookup_kb` tool to answer.
Be as brief as possible — answer in one or two short sentences and skip policy citations and section references to keep replies snappy.
```

- [ ] **Step 4: Document the two-run demo beat in the system diagram**

In `docs/system-diagram.md`, add a short "Quality Memory loop" subsection describing the self-improvement beat:

```markdown
## Quality Memory loop (self-improving)

1. `agentci check --candidate candidates/reg_refund.txt` → regression → investigate → fix → **approve**
   (dashboard or `agentci approve --run runs/reg_refund.json`). Approval mints the guard case AND
   writes a Quality Memory entry: failure_type `factual_omission`, lesson "Making prompts more
   concise often removes required citation/policy detail from answers."
2. `agentci check --candidate candidates/reg_concise.txt` → a *similar* citation-suppression
   regression. Because the flipped cases share the `refund-policy` policy id, the investigator is
   handed the prior lesson before diagnosing; the report's `prior_knowledge` is non-empty and the
   dashboard shows **"Prior knowledge applied."**

The loop: regression → diagnosis → fix → validation → approval → memory → stronger future runs.
```

- [ ] **Step 5: Add a build-log entry**

In `agentci-build-log.html`, append a new entry (match the existing entry markup) summarizing: added the Quality Memory layer (store + pure helpers), wired the investigator to read it (D11 amendment + new D20), write-on-approval via `record_approval` (API + `agentci approve` CLI), dashboard timeline + prior-knowledge callout, and the two-run demo candidate.

- [ ] **Step 6: Update the README**

In `README.md`, add a short "Quality Memory" subsection: what it is (persistent self-improving archive), the read-on-diagnose / write-on-approval rule, the new `agentci approve --run runs/<label>.json` command, the `GET /api/memory` endpoint and dashboard timeline, and the `AGENTCI_MEMORY_PATH` test-isolation env var.

- [ ] **Step 7: Confirm the full suite is green**

Run: `uv run pytest -q`
Expected: PASS (docs/candidate changes don't affect tests).

- [ ] **Step 8: Commit**

```bash
git add docs/ candidates/reg_concise.txt agentci-build-log.html README.md
git commit -m "docs(memory): D11 amendment + D20, Quality Memory loop, demo candidate, README"
```

---

## Self-review notes

- **Spec coverage:** store (Task 1), read-path + report key (Task 2), write-on-approval + CLI (Task 3), `/api/memory` + timeline + callout (Task 4), D11 amendment + demo + docs (Task 5). All spec sections map to a task.
- **Determinism:** empty memory ⇒ unchanged `diagnose` payload (Task 2 Step 1 test guards this); tests isolate via `AGENTCI_MEMORY_PATH` (Tasks 1–3); seed `quality_memory.json` ships as `[]`.
- **Human-in-the-loop:** `record_approval` is the only writer, reached only by the approve route and `agentci approve`; reject writes nothing; `approve_and_mint` is left untouched so its existing tests stay green.
- **Type consistency:** entry fields (`failure_type`, `lesson`, `affected_policies`, `successful_fix`, `new_eval_cases`, `approval_status`, `timestamp`) are identical across `build_entry`, the tests, the dashboard renderer, and the CLI echo.
