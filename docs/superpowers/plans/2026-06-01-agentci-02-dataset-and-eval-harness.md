# AgentCI Plan 02 — Synthetic Dataset + Eval Harness

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Depends on Plan 01** (uses `agentci.config`, `agentci.cache`, `agentci.target.run.answer_ticket`).

**Goal:** Generate a synthetic SaaS-billing KB + 40 gold-resolution tickets, freeze them to disk, upload as a single Phoenix dataset with a fixed 60/40 tune/held-out split (D3), implement four LLM-as-judge evaluators (D6), and produce the **baseline experiment** with per-case 0–1 scores.

**Architecture:** Generation is a one-shot script (run once, output committed as `kb.json`/`tickets.json` — synthetic-for-control, GAP-5). `dataset.py` uploads the frozen tickets to Phoenix with `split` and `source` metadata. `evals/judges.py` defines four Phoenix evaluator functions, each a `gemini-2.5-pro` judge returning a 0–1 score + explanation, cached for determinism. `evals/experiment.py` wraps `client.experiments.run_experiment` to run a candidate prompt over a partition and return per-case scores.

**Tech Stack:** arize-phoenix-client, google-genai, pandas, pytest (+ Plan 01 stack).

---

## File structure (this plan)

- Create `agentci/data/__init__.py`
- Create `agentci/data/generate.py` — Gemini-generate KB + 40 tickets (one-shot).
- Create `agentci/data/kb.json` — frozen KB (committed output of generate).
- Create `agentci/data/tickets.json` — frozen 40 tickets w/ gold + split tags.
- Create `agentci/data/dataset.py` — load frozen tickets, assign split, upload to Phoenix.
- Create `agentci/evals/__init__.py`
- Create `agentci/evals/judges.py` — 4 LLM-judge evaluators + score parsing (D6).
- Create `agentci/evals/experiment.py` — run_experiment wrapper → per-case scores.
- Tests under `tests/`.

---

### Task 1: Ticket schema + split assignment (pure logic, testable first)

**Files:**
- Create: `agentci/data/__init__.py`
- Create: `agentci/data/dataset.py` (split logic only this task; Phoenix upload in Task 5)
- Test: `tests/test_split.py`

Split rule (D3): tickets are ordered by `id`; the first 60% → `tune`, last 40% → `held_out`. Deterministic, no randomness.

- [ ] **Step 1: Write `agentci/data/__init__.py`**

```python
```

(empty)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_split.py
from agentci.data.dataset import assign_splits

def test_60_40_split_is_deterministic_and_ordered():
    tickets = [{"id": f"t{i:02d}"} for i in range(40)]
    out = assign_splits(tickets)
    tune = [t for t in out if t["split"] == "tune"]
    held = [t for t in out if t["split"] == "held_out"]
    assert len(tune) == 24 and len(held) == 16        # D3
    assert tune[0]["id"] == "t00" and held[0]["id"] == "t24"
    # source defaults to "seed"
    assert all(t["source"] == "seed" for t in out)

def test_split_rounds_down_tune_for_small_sets():
    tickets = [{"id": f"t{i}"} for i in range(10)]
    out = assign_splits(tickets)
    assert sum(t["split"] == "tune" for t in out) == 6
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_split.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.data.dataset'`.

- [ ] **Step 4: Write `agentci/data/dataset.py` (split logic only)**

```python
"""Frozen-ticket loading, split assignment, and Phoenix dataset upload."""
import json
import math
from pathlib import Path

_TICKETS_PATH = Path(__file__).resolve().parent / "tickets.json"


def assign_splits(tickets: list[dict]) -> list[dict]:
    """Assign a deterministic 60/40 tune/held_out split by sorted id (D3).

    Adds 'split' ('tune'|'held_out') and 'source' ('seed') if not present.
    """
    ordered = sorted(tickets, key=lambda t: t["id"])
    cutoff = math.floor(len(ordered) * 0.6)
    out = []
    for i, t in enumerate(ordered):
        t = dict(t)
        t["split"] = "tune" if i < cutoff else "held_out"
        t.setdefault("source", "seed")
        out.append(t)
    return out


def load_tickets() -> list[dict]:
    """Load frozen tickets from disk with splits assigned."""
    raw = json.loads(_TICKETS_PATH.read_text(encoding="utf-8"))
    return assign_splits(raw)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_split.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add agentci/data/__init__.py agentci/data/dataset.py tests/test_split.py
git commit -m "feat: deterministic 60/40 tune/held-out split"
```

---

### Task 2: Generation script (one-shot, produces frozen data)

**Files:**
- Create: `agentci/data/generate.py`
- Test: `tests/test_generate.py`

`generate.py` is a script run **once** by a human; its outputs (`kb.json`, `tickets.json`) are committed and become the source of truth. We unit-test only the validation helper that guards output shape, because generation itself is a live Gemini call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generate.py
import pytest
from agentci.data.generate import validate_tickets, validate_kb, TicketShapeError

def test_validate_tickets_requires_fields():
    good = [{"id": "t00", "question": "q", "gold_resolution": "a", "policy_id": "refund-policy"}]
    validate_tickets(good)  # no raise

def test_validate_tickets_rejects_missing_gold():
    with pytest.raises(TicketShapeError):
        validate_tickets([{"id": "t00", "question": "q"}])

def test_validate_kb_requires_unique_ids():
    with pytest.raises(TicketShapeError):
        validate_kb([{"id": "x", "title": "a", "body": "b"},
                     {"id": "x", "title": "c", "body": "d"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.data.generate'`.

- [ ] **Step 3: Write `agentci/data/generate.py`**

```python
"""ONE-SHOT generator: synthesize a SaaS-billing KB and 40 gold-resolution tickets.

Run by a human once; commit the resulting kb.json / tickets.json. Synthetic by design
(D7 / GAP-5) so the demo regression is scriptable and repeatable.

Usage:
    uv run python -m agentci.data.generate
"""
import json
from pathlib import Path

from google import genai

from agentci import config

_HERE = Path(__file__).resolve().parent


class TicketShapeError(ValueError):
    """Raised when generated data does not match the required schema."""


_REQUIRED_TICKET_FIELDS = {"id", "question", "gold_resolution", "policy_id"}


def validate_tickets(tickets: list[dict]) -> None:
    if len(tickets) < 1:
        raise TicketShapeError("no tickets")
    ids = set()
    for t in tickets:
        missing = _REQUIRED_TICKET_FIELDS - t.keys()
        if missing:
            raise TicketShapeError(f"ticket {t.get('id')} missing {missing}")
        if t["id"] in ids:
            raise TicketShapeError(f"duplicate ticket id {t['id']}")
        ids.add(t["id"])


def validate_kb(sections: list[dict]) -> None:
    ids = set()
    for s in sections:
        if not {"id", "title", "body"} <= s.keys():
            raise TicketShapeError(f"kb section missing fields: {s}")
        if s["id"] in ids:
            raise TicketShapeError(f"duplicate kb id {s['id']}")
        ids.add(s["id"])


_KB_PROMPT = """Generate a knowledge base for a SaaS billing product as JSON: a list of
8-12 objects with keys "id" (kebab-case), "title", "body" (2-4 sentences of concrete policy).
Cover at minimum: refund policy (14-day window, monthly-only eligibility, 5-business-day
posting), billing cycle, plan upgrades/downgrades, failed payments, cancellation, invoices,
seat management, tax/VAT. Return ONLY the JSON array."""


def _tickets_prompt(kb_json: str) -> str:
    return f"""Given this knowledge base JSON:\n{kb_json}\n
Generate 40 customer-support tickets as a JSON array. Each object has keys:
"id" ("t00".."t39"), "question" (a realistic customer message), "gold_resolution"
(the correct answer grounded ONLY in the KB, citing the relevant policy), and
"policy_id" (the KB section id the answer relies on). Spread questions across all KB
topics; include several refund-policy questions. Return ONLY the JSON array."""


def _gen(prompt: str) -> list[dict]:
    client = genai.Client()
    resp = client.models.generate_content(
        model=config.ENGINEER_MODEL,
        contents=prompt,
        config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
    )
    return json.loads(resp.text)


def main() -> None:
    kb = _gen(_KB_PROMPT)
    validate_kb(kb)
    (_HERE / "kb.json").write_text(json.dumps(kb, indent=2), encoding="utf-8")

    tickets = _gen(_tickets_prompt(json.dumps(kb)))
    validate_tickets(tickets)
    (_HERE / "tickets.json").write_text(json.dumps(tickets, indent=2), encoding="utf-8")
    print(f"wrote {len(kb)} KB sections and {len(tickets)} tickets")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_generate.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Generate the frozen data (live, one-shot)**

Run: `uv run python -m agentci.data.generate`
Expected: prints `wrote N KB sections and 40 tickets`; creates `agentci/data/kb.json` and `agentci/data/tickets.json`.

> If Gemini returns 39 or 41 tickets, hand-edit `tickets.json` to exactly 40 with ids `t00`..`t39` (the split test assumes 40). Re-run `tests/test_split.py::test_60_40_split_is_deterministic_and_ordered` against the real file count is NOT required — that test uses synthetic ids.

- [ ] **Step 6: Commit the frozen data**

```bash
git add agentci/data/generate.py agentci/data/kb.json agentci/data/tickets.json tests/test_generate.py
git commit -m "feat: one-shot generator + frozen synthetic KB and 40 tickets"
```

---

### Task 3: Score parsing for judges (pure logic)

**Files:**
- Create: `agentci/evals/__init__.py`
- Create: `agentci/evals/judges.py` (parsing helper this task; judges in Task 4)
- Test: `tests/test_judge_parsing.py`

Each judge prompt asks the model to return JSON `{"score": <0..1 float>, "explanation": "..."}`. `parse_judge_response` must clamp to [0,1] and tolerate fenced code blocks.

- [ ] **Step 1: Write `agentci/evals/__init__.py`**

```python
```

(empty)

- [ ] **Step 2: Write the failing test**

```python
# tests/test_judge_parsing.py
from agentci.evals.judges import parse_judge_response

def test_parses_plain_json():
    out = parse_judge_response('{"score": 0.8, "explanation": "good"}')
    assert out == {"score": 0.8, "explanation": "good"}

def test_strips_code_fence_and_clamps():
    raw = "```json\n{\"score\": 1.4, \"explanation\": \"over\"}\n```"
    out = parse_judge_response(raw)
    assert out["score"] == 1.0

def test_missing_score_defaults_to_zero():
    out = parse_judge_response("not json at all")
    assert out["score"] == 0.0
    assert "explanation" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_judge_parsing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.evals.judges'`.

- [ ] **Step 4: Write parsing helper into `agentci/evals/judges.py`**

```python
"""LLM-as-judge evaluators (D6): correctness, groundedness, completeness, policy_reference."""
import json
import re

from google import genai

from agentci import cache, config

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_judge_response(raw: str) -> dict:
    """Parse a judge response into {"score": float in [0,1], "explanation": str}."""
    text = raw.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        score = float(data.get("score", 0.0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"score": 0.0, "explanation": f"unparseable judge output: {raw[:120]}"}
    score = max(0.0, min(1.0, score))
    return {"score": score, "explanation": str(data.get("explanation", ""))}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_judge_parsing.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add agentci/evals/__init__.py agentci/evals/judges.py tests/test_judge_parsing.py
git commit -m "feat: robust judge-response parsing"
```

---

### Task 4: The four LLM-judge evaluators

**Files:**
- Modify: `agentci/evals/judges.py` (append)
- Test: `tests/test_judges.py`

Each evaluator is a function `(output, expected, metadata) -> float` (Phoenix evaluator signature; param names are bound by Phoenix). All calls are cached (D7). We test wiring via replay, not live judgments.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judges.py
import json
from agentci import cache
from agentci.evals import judges

def _seed(tmp_path, dimension, output, expected, kb, score):
    payload = {"dimension": dimension, "output": output, "expected": expected, "kb": kb}
    path = tmp_path / (cache._key("judge", payload) + ".json")
    path.write_text(json.dumps({"score": score, "explanation": "x"}))

def test_correctness_evaluator_returns_cached_score(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    md = {"kb": "KB", "policy_id": "refund-policy"}
    _seed(tmp_path, "correctness", "ans", "gold", "KB", 0.9)
    score = judges.correctness(output={"answer": "ans"}, expected={"gold_resolution": "gold"}, metadata=md)
    assert score == 0.9

def test_all_four_dimensions_exist():
    assert {f.__name__ for f in judges.ALL_EVALUATORS} == {
        "correctness", "groundedness", "completeness", "policy_reference"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_judges.py -v`
Expected: FAIL with `AttributeError: module 'agentci.evals.judges' has no attribute 'correctness'`.

- [ ] **Step 3: Append the evaluators to `agentci/evals/judges.py`**

```python
_RUBRICS = {
    "correctness": "Does the ANSWER match the GOLD resolution in substance? "
                   "1.0 = fully correct, 0.0 = wrong or contradictory.",
    "groundedness": "Is every claim in the ANSWER supported by the KNOWLEDGE BASE? "
                    "Penalize any invented policy. 1.0 = fully grounded, 0.0 = hallucinated.",
    "completeness": "Does the ANSWER fully resolve the request (or correctly route it), "
                    "covering all conditions the GOLD resolution covers? 1.0 = complete.",
    "policy_reference": "Does the ANSWER cite/reference the correct policy section "
                        "(expected policy id given)? 1.0 = correct citation, 0.0 = none/wrong.",
}


def _judge(dimension: str, output: dict, expected: dict, metadata: dict) -> float:
    answer = (output or {}).get("answer", "")
    gold = (expected or {}).get("gold_resolution", "")
    kb = (metadata or {}).get("kb", "")
    payload = {"dimension": dimension, "output": answer, "expected": gold, "kb": kb}

    def live():
        client = genai.Client()
        prompt = (
            f"You are a strict evaluator. RUBRIC: {_RUBRICS[dimension]}\n\n"
            f"KNOWLEDGE BASE:\n{kb}\n\nGOLD RESOLUTION:\n{gold}\n\n"
            f"EXPECTED POLICY ID: {(metadata or {}).get('policy_id','')}\n\n"
            f"ANSWER UNDER TEST:\n{answer}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>, "explanation": "<one sentence>"}'
        )
        resp = client.models.generate_content(
            model=config.JUDGE_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return parse_judge_response(resp.text)

    return cache.cached("judge", payload, live)["score"]


def correctness(output, expected, metadata) -> float:
    return _judge("correctness", output, expected, metadata)


def groundedness(output, expected, metadata) -> float:
    return _judge("groundedness", output, expected, metadata)


def completeness(output, expected, metadata) -> float:
    return _judge("completeness", output, expected, metadata)


def policy_reference(output, expected, metadata) -> float:
    return _judge("policy_reference", output, expected, metadata)


ALL_EVALUATORS = [correctness, groundedness, completeness, policy_reference]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_judges.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agentci/evals/judges.py tests/test_judges.py
git commit -m "feat: four LLM-as-judge evaluators (D6)"
```

---

### Task 5: Phoenix dataset upload

**Files:**
- Modify: `agentci/data/dataset.py` (append upload fn)
- Test: `tests/test_dataset_upload.py`

`upload_dataset()` builds a dataframe from `load_tickets()` and calls `client.datasets.create_dataset` with `input_keys=["question"]`, `output_keys=["gold_resolution"]`, and `metadata` columns `policy_id`, `split`, `source`, `kb`. We test dataframe construction (pure) and mock the client for the call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset_upload.py
from unittest.mock import MagicMock
from agentci.data import dataset

def test_build_dataframe_has_metadata_columns():
    df = dataset.build_dataframe()
    for col in ["question", "gold_resolution", "policy_id", "split", "source", "kb"]:
        assert col in df.columns
    assert df["split"].isin(["tune", "held_out"]).all()
    assert (df["kb"].str.len() > 0).all()  # KB embedded for grounded judging

def test_upload_calls_create_dataset(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(dataset, "_client", lambda: client)
    dataset.upload_dataset()
    args, kwargs = client.datasets.create_dataset.call_args
    assert kwargs["input_keys"] == ["question"]
    assert kwargs["output_keys"] == ["gold_resolution"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dataset_upload.py -v`
Expected: FAIL with `AttributeError: module 'agentci.data.dataset' has no attribute 'build_dataframe'`.

- [ ] **Step 3: Append to `agentci/data/dataset.py`**

```python
import pandas as pd
from phoenix.client import Client

from agentci import config

_KB_PATH = Path(__file__).resolve().parent / "kb.json"


def _client() -> Client:
    return Client()


def _kb_text() -> str:
    return json.dumps(json.loads(_KB_PATH.read_text(encoding="utf-8")))


def build_dataframe() -> "pd.DataFrame":
    """Build the upload dataframe: inputs, gold output, and metadata (split/source/policy/kb)."""
    kb = _kb_text()
    rows = []
    for t in load_tickets():
        rows.append({
            "id": t["id"],
            "question": t["question"],
            "gold_resolution": t["gold_resolution"],
            "policy_id": t["policy_id"],
            "split": t["split"],
            "source": t["source"],
            "kb": kb,
        })
    return pd.DataFrame(rows)


def upload_dataset(name: str | None = None):
    """Upload the frozen suite to Phoenix as the single source of truth (spec §6)."""
    df = build_dataframe()
    return _client().datasets.create_dataset(
        name=name or config.DATASET_NAME,
        dataframe=df,
        input_keys=["question"],
        output_keys=["gold_resolution"],
        metadata_keys=["policy_id", "split", "source", "kb", "id"],
    )
```

> Confirm the exact `create_dataset` keyword for metadata columns (`metadata_keys`) against the installed `arize-phoenix-client` version; if the param differs (e.g. `metadata`), adjust this single call. The dataframe contract above is what later plans depend on.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dataset_upload.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Upload for real (live)**

Run: `uv run python -c "from agentci.data.dataset import upload_dataset; print(upload_dataset())"`
Expected: dataset `agentci-support-suite` appears in Phoenix with 40 examples and split metadata.

- [ ] **Step 6: Commit**

```bash
git add agentci/data/dataset.py tests/test_dataset_upload.py
git commit -m "feat: upload support suite to Phoenix with split metadata"
```

---

### Task 6: Experiment wrapper → per-case scores

**Files:**
- Create: `agentci/evals/experiment.py`
- Test: `tests/test_experiment.py`

`run_candidate(prompt, split, experiment_name)` runs the target agent (Plan 01 `answer_ticket`) over the chosen partition as a Phoenix experiment with the four judges, then returns a normalized per-case score table: `[{"id","split","scores":{dim:float},"passed":bool}, ...]`. `passed` uses D9 (all dims ≥ 0.7). We test the normalization/pass logic against a stubbed experiment object.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experiment.py
from agentci.evals import experiment

def test_passed_requires_all_dims_above_threshold():
    scores = {"correctness": 0.9, "groundedness": 0.8, "completeness": 0.75, "policy_reference": 0.7}
    assert experiment.case_passed(scores) is True
    scores["policy_reference"] = 0.69
    assert experiment.case_passed(scores) is False

def test_normalize_results_shapes_rows():
    raw = [
        {"id": "t00", "split": "tune",
         "scores": {"correctness": 0.9, "groundedness": 0.9, "completeness": 0.9, "policy_reference": 0.9}},
        {"id": "t01", "split": "held_out",
         "scores": {"correctness": 0.2, "groundedness": 0.9, "completeness": 0.9, "policy_reference": 0.9}},
    ]
    rows = experiment.normalize_results(raw)
    assert rows[0]["passed"] is True
    assert rows[1]["passed"] is False
    assert rows[1]["split"] == "held_out"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_experiment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agentci.evals.experiment'`.

- [ ] **Step 3: Write `agentci/evals/experiment.py`**

```python
"""Run a candidate prompt over a dataset partition as a Phoenix experiment -> per-case scores."""
from phoenix.client import Client

from agentci import config
from agentci.evals.judges import ALL_EVALUATORS
from agentci.target.run import answer_ticket


def case_passed(scores: dict) -> bool:
    """A case passes overall iff every rubric dimension meets the threshold (D9)."""
    return all(scores.get(dim, 0.0) >= config.PASS_THRESHOLD for dim in config.RUBRIC_DIMENSIONS)


def normalize_results(raw_rows: list[dict]) -> list[dict]:
    """Attach the overall 'passed' flag to each per-case score row."""
    out = []
    for r in raw_rows:
        row = dict(r)
        row["passed"] = case_passed(r["scores"])
        out.append(row)
    return out


def _client() -> Client:
    return Client()


def run_candidate(prompt: str, dataset_name: str, split: str, experiment_name: str) -> list[dict]:
    """Run the target agent (with `prompt`) over `split` of the dataset as a Phoenix experiment.

    Returns normalized per-case rows: {"id","split","scores":{dim:float},"passed":bool}.
    """
    client = _client()
    dataset = client.datasets.get_dataset(name=dataset_name)

    def task(input, metadata):  # noqa: A002 - Phoenix binds these param names
        return answer_ticket(prompt, input["question"])

    experiment = client.experiments.run_experiment(
        dataset=dataset,
        task=task,
        evaluators=ALL_EVALUATORS,
        experiment_name=experiment_name,
    )

    raw = []
    for rec in experiment.as_dataframe().itertuples():
        md = getattr(rec, "metadata", {}) or {}
        if md.get("split") != split:
            continue
        raw.append({
            "id": md.get("id"),
            "split": md.get("split"),
            "answer": (getattr(rec, "output", {}) or {}).get("answer", ""),  # carried for clustering (Plan 03)
            "scores": {dim: float(getattr(rec, dim, 0.0)) for dim in config.RUBRIC_DIMENSIONS},
        })
    return normalize_results(raw)
```

> Per-case row contract (consumed by Plan 03): `{"id", "split", "answer", "scores":{dim:float}, "passed":bool}`. The `answer` field is the candidate agent's output text, used by the failure-clustering step.

> The result-extraction (`experiment.as_dataframe()`, column names per evaluator) must be confirmed against the installed client — annotation columns may be named `eval.<name>.score`. Adjust the extraction loop only; keep the returned row shape exactly as documented (the Engineer loop in Plan 03 depends on it).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_experiment.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Produce the baseline experiment (live)**

Run: `uv run python -c "from agentci.tracing import init_tracing; from agentci.evals.experiment import run_candidate; from agentci import config; import os; os.environ['AGENTCI_CACHE_MODE']='record'; init_tracing(); rows=run_candidate(config.BASELINE_SUPPORT_PROMPT, config.DATASET_NAME, 'tune', 'baseline-tune'); print(len(rows), sum(r['passed'] for r in rows))"`
Expected: prints `24 <n_pass>`; a `baseline-tune` experiment appears in Phoenix; judge fixtures cached for replay.

- [ ] **Step 6: Commit**

```bash
git add agentci/evals/experiment.py tests/test_experiment.py .agentci_cache
git commit -m "feat: experiment wrapper, per-case scores, baseline experiment + fixtures"
```

---

## Self-review (Plan 02)

- **Spec coverage:** synthetic KB + 40 gold tickets ✓ (§6), Phoenix dataset as single source of truth ✓, 60/40 split ✓ (D3/GAP-3), four LLM-judge rubric ✓ (§7/D6), baseline experiment with per-case scores ✓ (§5.3), determinism via cache ✓ (GAP-5).
- **Placeholder scan:** none. Two verify-and-adjust notes (create_dataset metadata kwarg; experiment result extraction) are real API-confirmation steps, with the stable contract pinned around them.
- **Type consistency:** `answer_ticket(prompt, ticket) -> {"answer"}` (Plan 01) consumed by `task`; per-case row `{"id","split","scores":{dim},"passed"}` is the contract Plan 03 consumes; `RUBRIC_DIMENSIONS`, `PASS_THRESHOLD` from `config`.

**Done when:** all pytest tests green AND the baseline experiment exists in Phoenix with per-case scores for the 4 dimensions and split metadata visible.
