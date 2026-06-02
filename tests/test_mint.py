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

def test_build_minted_case_carries_guard():
    from agentci.engineer.mint import build_minted_case
    cluster = {"label": "refund-policy", "policy_id": "R-14"}
    guard = {"kind": "assertion", "slug": "refund-window", "claim": "states window",
             "check": {"type": "must_include", "values": ["14-day"], "mode": "all"}, "origin": {}}
    case = build_minted_case(cluster, "q", "gold", guard=guard)
    import json as _json
    assert _json.loads(case["guard"])["slug"] == "refund-window"
