"""Maps logical experiment names (e.g. 'baseline-tune') to the Phoenix experiment IDs that
run_experiment assigns. Phoenix Cloud stores experiments anonymously (no searchable name), so the
runtime MCP read fetches them BY ID — this registry is how the check finds the right experiment.

Persisted to a small JSON file so the IDs survive across processes (the baseline-recording run and
the later `agentci check` run). Git-ignored alongside the cache — it is per-Phoenix-space state.
"""
import json
import os
from pathlib import Path

_PATH = Path(os.environ.get("AGENTCI_EXPERIMENTS_FILE", ".agentci_experiments.json"))


def _load() -> dict:
    if _PATH.exists():
        return json.loads(_PATH.read_text(encoding="utf-8"))
    return {}


def register(experiment_name: str, experiment_id: str) -> None:
    """Record (or overwrite) the Phoenix experiment ID for a logical experiment name."""
    data = _load()
    data[experiment_name] = experiment_id
    _PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_id(experiment_name: str) -> str:
    """Return the Phoenix experiment ID for a logical name, or raise if it was never recorded."""
    data = _load()
    if experiment_name not in data:
        raise KeyError(
            f"no Phoenix experiment id registered for {experiment_name!r}; "
            f"run the experiment first (known: {sorted(data)})"
        )
    return data[experiment_name]
