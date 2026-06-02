"""Mint a permanent eval case capturing the caught regression. Tune partition only (D5)."""
import json
from pathlib import Path

import pandas as pd
from phoenix.client import Client

from agentci import config

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "kb.json"


def _kb_text() -> str:
    return json.dumps(json.loads(_KB_PATH.read_text(encoding="utf-8")))


def build_minted_case(cluster: dict, question: str, gold: str, index: int = 0, guard: dict | None = None) -> dict:
    """Construct the new eval case row. Always split='tune', source='minted' (D5). Carries the
    authored guard spec (D15) as a JSON string in metadata."""
    label = cluster["label"]
    return {
        "id": f"minted-{label}-{index}",
        "question": question,
        "gold_resolution": gold,
        "policy_id": cluster["policy_id"],
        "split": "tune",
        "source": "minted",
        "kb": _kb_text(),
        "guard": json.dumps(guard or {}),
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
        metadata_keys=["policy_id", "split", "source", "kb", "id", "guard"],
    )


def approve_and_mint(report: dict, dataset_name: str | None = None) -> dict | None:
    """Persist the report's proposed minted case on human approval (D12).

    Returns the minted case that was persisted, or None if the report has nothing to mint.
    """
    case = report.get("proposed_mint")
    if not case:
        return None
    persist_minted_case(case, dataset_name)
    return case
