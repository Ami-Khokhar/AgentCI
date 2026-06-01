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
