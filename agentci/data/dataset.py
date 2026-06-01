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
