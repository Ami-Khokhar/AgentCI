# AgentCI Plan 01 — Target Agent + Tracing Foundations

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project, a Phoenix-traced, config-driven ADK support agent with a KB tool and a callable entrypoint, plus the record/replay cache that makes every later plan testable and the demo replayable.

**Architecture:** A `gemini-2.5-flash` ADK `Agent` whose system prompt is injected from a config object (so a "candidate" is just a different prompt string). A KB tool answers from a synthetic knowledge base. `phoenix.otel.register(auto_instrument=True)` streams OpenInference spans to Phoenix Cloud. A small file-backed cache records/replays model-shaped responses so tests are deterministic.

**Tech Stack:** Python 3.13, uv, google-adk, google-genai, arize-phoenix-otel, openinference-instrumentation-google-adk, pytest.

---

## File structure (this plan)

- Create `pyproject.toml` — project + deps + console scripts.
- Create `.env.example` — required env vars.
- Create `agentci/__init__.py` — package marker + version.
- Create `agentci/config.py` — pinned model IDs, temperatures, thresholds (D8/D9), prompt registry.
- Create `agentci/cache.py` — record/replay cache (D7).
- Create `agentci/tracing.py` — `phoenix.otel.register` wrapper.
- Create `agentci/target/__init__.py`.
- Create `agentci/target/kb.py` — KB accessor + ADK tool function.
- Create `agentci/target/agent.py` — config-driven ADK support agent factory.
- Create `agentci/target/run.py` — callable entrypoint `answer_ticket(prompt, ticket) -> dict`.
- Tests under `tests/`.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `agentci/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "agentci"
version = "0.1.0"
description = "Regression CI for AI agents"
requires-python = ">=3.13"
dependencies = [
    "google-adk>=1.0.0",
    "google-genai>=1.0.0",
    "arize-phoenix-otel>=0.6.0",
    "arize-phoenix-client>=1.0.0",
    "openinference-instrumentation-google-adk>=0.1.0",
    "python-dotenv>=1.0.0",
    "pandas>=2.2.0",
    "click>=8.1.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]

[project.scripts]
agentci = "agentci.cli:cli"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Write `.env.example`**

```bash
# Phoenix Cloud
PHOENIX_API_KEY=px_live_xxxxxxxx
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/s/your-space
PHOENIX_BASE_URL=https://app.phoenix.arize.com/s/your-space
PHOENIX_PROJECT_NAME=agentci

# Gemini (AI Studio key; or set Vertex vars instead)
GOOGLE_API_KEY=xxxxxxxx

# AgentCI behavior
AGENTCI_CACHE_MODE=replay   # replay | record | live
AGENTCI_CACHE_DIR=.agentci_cache
```

- [ ] **Step 3: Write `agentci/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Install and verify the env resolves**

Run: `uv sync --extra dev`
Expected: resolves and installs without error; creates `.venv`.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml .env.example agentci/__init__.py
git commit -m "chore: project scaffold and dependencies"
```

---

### Task 2: Config (models, temps, thresholds, prompt registry)

**Files:**
- Create: `agentci/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from agentci import config

def test_thresholds_match_frozen_decisions():
    assert config.PASS_THRESHOLD == 0.7          # D9
    assert config.MIN_HELDOUT_LIFT == 0.05        # D8
    assert config.MAX_HELDOUT_REGRESSIONS == 0    # D8

def test_models_are_pinned_and_deterministic():
    assert config.TARGET_MODEL == "gemini-2.5-flash"
    assert config.ENGINEER_MODEL == "gemini-2.5-pro"
    assert config.JUDGE_MODEL == "gemini-2.5-pro"
    assert config.TEMPERATURE == 0.0             # D7

def test_baseline_prompt_is_registered():
    assert "refund" in config.BASELINE_SUPPORT_PROMPT.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.config'`.

- [ ] **Step 3: Write `agentci/config.py`**

```python
"""Single source of truth for model IDs, determinism, thresholds (frozen decisions)."""

# --- Models (pinned for determinism, D7) ---
TARGET_MODEL = "gemini-2.5-flash"
ENGINEER_MODEL = "gemini-2.5-pro"
JUDGE_MODEL = "gemini-2.5-pro"
TEMPERATURE = 0.0

# --- Rubric thresholds (D9) ---
PASS_THRESHOLD = 0.7          # per-dimension score >= this => "pass"

# --- Promotion gate (D8) ---
MIN_HELDOUT_LIFT = 0.05       # candidate mean correctness must beat baseline by >= this
MAX_HELDOUT_REGRESSIONS = 0   # zero held-out pass->fail flips allowed

# --- Phoenix dataset naming ---
DATASET_NAME = "agentci-support-suite"
RUBRIC_DIMENSIONS = ("correctness", "groundedness", "completeness", "policy_reference")

# --- Baseline target-agent system prompt ---
BASELINE_SUPPORT_PROMPT = """You are a customer-support agent for a SaaS billing product.
Use ONLY the knowledge base returned by the `lookup_kb` tool to answer.
Always cite the exact policy section you relied on. If the knowledge base does not
cover the question, say you will route the ticket to a human and name the team.
For refund questions, state the refund window and any eligibility conditions explicitly."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/config.py tests/test_config.py
git commit -m "feat: config with pinned models and frozen thresholds"
```

---

### Task 3: Record/replay cache (determinism, D7)

**Files:**
- Create: `agentci/cache.py`
- Test: `tests/test_cache.py`

The cache keys a deterministic hash of `(namespace, payload)` to a stored JSON value. In `replay` mode it returns the stored value and errors if missing; in `record` mode it calls the live function and stores the result; in `live` mode it bypasses storage.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
import json
from agentci import cache

def test_record_then_replay_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "record")
    calls = {"n": 0}

    def live():
        calls["n"] += 1
        return {"text": "hello"}

    out1 = cache.cached("judge", {"q": 1}, live)
    assert out1 == {"text": "hello"}
    assert calls["n"] == 1

    # Switch to replay: the live fn must NOT be called again.
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    out2 = cache.cached("judge", {"q": 1}, live)
    assert out2 == {"text": "hello"}
    assert calls["n"] == 1  # unchanged

def test_replay_miss_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    try:
        cache.cached("judge", {"q": 999}, lambda: {"text": "x"})
        assert False, "expected CacheMissError"
    except cache.CacheMissError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.cache'`.

- [ ] **Step 3: Write `agentci/cache.py`**

```python
"""Record/replay cache: makes LLM-touching code deterministic for tests and demo replay."""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable


class CacheMissError(RuntimeError):
    """Raised in replay mode when no recording exists for the key."""


def _mode() -> str:
    return os.environ.get("AGENTCI_CACHE_MODE", "replay")


def _dir() -> Path:
    d = Path(os.environ.get("AGENTCI_CACHE_DIR", ".agentci_cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(namespace: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return f"{namespace}-{digest}"


def cached(namespace: str, payload: Any, live_fn: Callable[[], Any]) -> Any:
    """Return live_fn() result, recording/replaying per AGENTCI_CACHE_MODE."""
    mode = _mode()
    if mode == "live":
        return live_fn()

    path = _dir() / f"{_key(namespace, payload)}.json"
    if mode == "replay":
        if not path.exists():
            raise CacheMissError(f"no recording for {namespace} key {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    if mode == "record":
        result = live_fn()
        path.write_text(json.dumps(result, default=str), encoding="utf-8")
        return result

    raise ValueError(f"unknown AGENTCI_CACHE_MODE: {mode}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/cache.py tests/test_cache.py
git commit -m "feat: record/replay cache for deterministic LLM tests"
```

---

### Task 4: Tracing wrapper

**Files:**
- Create: `agentci/tracing.py`
- Test: `tests/test_tracing.py`

- [ ] **Step 1: Write the failing test** (idempotency + project name; no live network)

```python
# tests/test_tracing.py
from unittest.mock import patch
from agentci import tracing

def test_init_tracing_calls_register_once(monkeypatch):
    monkeypatch.setenv("PHOENIX_PROJECT_NAME", "agentci-test")
    tracing._PROVIDER = None  # reset module state
    with patch("agentci.tracing.register") as reg:
        reg.return_value = "provider"
        first = tracing.init_tracing()
        second = tracing.init_tracing()
    assert first == "provider"
    assert second == "provider"
    reg.assert_called_once_with(project_name="agentci-test", auto_instrument=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tracing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.tracing'`.

- [ ] **Step 3: Write `agentci/tracing.py`**

```python
"""Phoenix tracing init. Mirrors the Arize reference repo's phoenix.otel.register usage."""
import os
from phoenix.otel import register

_PROVIDER = None


def init_tracing():
    """Idempotently register the Phoenix tracer; auto-instruments installed OI deps (ADK)."""
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = register(
            project_name=os.environ.get("PHOENIX_PROJECT_NAME", "agentci"),
            auto_instrument=True,
        )
    return _PROVIDER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tracing.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/tracing.py tests/test_tracing.py
git commit -m "feat: idempotent Phoenix tracing wrapper"
```

---

### Task 5: KB accessor + tool

**Files:**
- Create: `agentci/target/__init__.py`
- Create: `agentci/target/kb.py`
- Test: `tests/test_kb.py`

The real KB content lands in Plan 02 (`agentci/data/kb.json`). Here we build the accessor + ADK tool against a tiny built-in fallback so the agent is runnable before the dataset exists.

- [ ] **Step 1: Write `agentci/target/__init__.py`**

```python
```

(empty package marker)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_kb.py
from agentci.target import kb

def test_lookup_kb_returns_matching_section():
    result = kb.lookup_kb("refund window")
    assert result["status"] == "success"
    assert any("refund" in s["title"].lower() for s in result["sections"])

def test_lookup_kb_unknown_returns_empty_success():
    result = kb.lookup_kb("how to fly to the moon")
    assert result["status"] == "success"
    assert result["sections"] == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_kb.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.target.kb'`.

- [ ] **Step 4: Write `agentci/target/kb.py`**

```python
"""Knowledge-base accessor and the ADK tool the support agent calls."""
import json
from pathlib import Path

_FALLBACK_KB = [
    {
        "id": "refund-policy",
        "title": "Refund Policy",
        "body": "Customers may request a full refund within 14 days of a charge. "
                "Refunds require the subscription to be on a monthly plan; annual "
                "plans are prorated. Approved refunds post within 5 business days.",
    },
    {
        "id": "billing-cycle",
        "title": "Billing Cycle",
        "body": "Subscriptions renew on the calendar day of initial purchase. "
                "Invoices are emailed 3 days before renewal.",
    },
]

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "kb.json"


def _load_kb() -> list[dict]:
    if _KB_PATH.exists():
        return json.loads(_KB_PATH.read_text(encoding="utf-8"))
    return _FALLBACK_KB


def lookup_kb(query: str) -> dict:
    """Retrieve knowledge-base sections relevant to a support query.

    Args:
        query (str): The user's question or keywords to search the KB for.

    Returns:
        dict: {"status": "success", "sections": [{"id","title","body"}, ...]}.
    """
    q = query.lower()
    sections = [
        s for s in _load_kb()
        if any(word in (s["title"] + " " + s["body"]).lower() for word in q.split())
    ]
    return {"status": "success", "sections": sections}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_kb.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add agentci/target/__init__.py agentci/target/kb.py tests/test_kb.py
git commit -m "feat: KB accessor and lookup_kb ADK tool"
```

---

### Task 6: Config-driven support agent factory

**Files:**
- Create: `agentci/target/agent.py`
- Test: `tests/test_target_agent.py`

The factory takes a system prompt (a "candidate") and returns a configured ADK `Agent`. We test construction/wiring, not model output.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_target_agent.py
from agentci.target.agent import build_support_agent
from agentci import config

def test_agent_uses_given_prompt_and_pinned_model():
    agent = build_support_agent("CUSTOM PROMPT")
    assert agent.instruction == "CUSTOM PROMPT"
    assert agent.model == config.TARGET_MODEL
    tool_names = [getattr(t, "__name__", getattr(t, "name", "")) for t in agent.tools]
    assert "lookup_kb" in tool_names

def test_agent_defaults_to_baseline_prompt():
    agent = build_support_agent()
    assert agent.instruction == config.BASELINE_SUPPORT_PROMPT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_target_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.target.agent'`.

- [ ] **Step 3: Write `agentci/target/agent.py`**

```python
"""Factory for the config-driven support agent. A 'candidate' = a different prompt string."""
from google.adk.agents import Agent

from agentci import config
from agentci.target.kb import lookup_kb


def build_support_agent(system_prompt: str | None = None) -> Agent:
    """Build the support-resolution agent with the given system prompt.

    Args:
        system_prompt: The candidate prompt. Defaults to the frozen baseline.
    """
    return Agent(
        name="support_agent",
        model=config.TARGET_MODEL,
        description="Resolves SaaS billing support tickets using the knowledge base.",
        instruction=system_prompt or config.BASELINE_SUPPORT_PROMPT,
        tools=[lookup_kb],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_target_agent.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/target/agent.py tests/test_target_agent.py
git commit -m "feat: config-driven support agent factory"
```

---

### Task 7: Callable entrypoint `answer_ticket`

**Files:**
- Create: `agentci/target/run.py`
- Test: `tests/test_target_run.py`

`answer_ticket(prompt, ticket)` runs the agent once and returns `{"answer": str}`. It is wrapped in the record/replay cache so tests and the demo are deterministic. The cache key is `(prompt, ticket)`.

- [ ] **Step 1: Write the failing test** (replay a recorded response; no live call)

```python
# tests/test_target_run.py
import json
from pathlib import Path
from agentci import cache
from agentci.target import run

def test_answer_ticket_replays_cached_response(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    # Pre-seed a recording under the exact key answer_ticket will compute.
    key_payload = {"prompt": "P", "ticket": "How do refunds work?"}
    digest_path = tmp_path / (cache._key("target", key_payload) + ".json")
    digest_path.write_text(json.dumps({"answer": "Refunds within 14 days."}))

    out = run.answer_ticket("P", "How do refunds work?")
    assert out == {"answer": "Refunds within 14 days."}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_target_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.target.run'`.

- [ ] **Step 3: Write `agentci/target/run.py`**

```python
"""Callable entrypoint for the support agent: (prompt, ticket) -> {"answer": ...}."""
import asyncio
import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from agentci import cache, config
from agentci.target.agent import build_support_agent


async def _run_once(system_prompt: str, ticket: str) -> str:
    agent = build_support_agent(system_prompt)
    runner = InMemoryRunner(agent=agent, app_name="agentci-target")
    user_id, session_id = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-target", user_id=user_id, session_id=session_id
    )
    final = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=ticket)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def answer_ticket(prompt: str, ticket: str) -> dict:
    """Run the support agent on one ticket. Cached for determinism (D7)."""
    payload = {"prompt": prompt, "ticket": ticket}
    return cache.cached("target", payload, lambda: {"answer": asyncio.run(_run_once(prompt, ticket))})
```

> Note: ADK's `InMemoryRunner`/event API is current as of ADK Python 2.0. If `event.is_final_response()` is unavailable in the installed version, confirm the final-event predicate in the ADK docs and adjust this one line — do not change the function's return contract.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_target_run.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/target/run.py tests/test_target_run.py
git commit -m "feat: cached callable entrypoint answer_ticket"
```

---

### Task 8: Manual live smoke (not a pytest test)

- [ ] **Step 1: Record a real traced run**

```bash
cp .env.example .env   # fill in real PHOENIX_* and GOOGLE_API_KEY
uv run python -c "from agentci.tracing import init_tracing; from agentci.target.run import answer_ticket; import os; os.environ['AGENTCI_CACHE_MODE']='record'; init_tracing(); print(answer_ticket(__import__('agentci.config',fromlist=['x']).BASELINE_SUPPORT_PROMPT, 'How do refunds work?'))"
```

Expected: prints a grounded answer mentioning the 14-day refund window; a `.agentci_cache/target-*.json` file is written.

- [ ] **Step 2: Confirm spans in Phoenix**

Open your Phoenix space → project `agentci`. Expected: an LLM span and a `lookup_kb` tool span for the run.

- [ ] **Step 3: Commit the recorded fixture (enables replay everywhere)**

```bash
git add .agentci_cache
git commit -m "test: record baseline target run fixture for replay"
```

---

## Self-review (Plan 01)

- **Spec coverage:** target agent ✓ (config-driven prompt = candidate mechanism), OpenInference→Phoenix tracing ✓, callable entrypoint ✓ (contract §4.B), determinism cache ✓ (GAP-5). KB content is intentionally deferred to Plan 02.
- **Placeholder scan:** none — every code step is complete. The one ADK-version caveat (Task 7) is a verify-and-adjust note, not a placeholder.
- **Type consistency:** `answer_ticket -> {"answer": str}` is the contract consumed by Plan 02's task function; `lookup_kb -> {"status","sections"}` is stable; `cache.cached(namespace, payload, live_fn)` and `cache._key` are reused verbatim by later plans.

**Done when:** all pytest tests green AND the Task 8 live smoke shows spans in Phoenix and writes a replayable fixture.
