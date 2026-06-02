from unittest.mock import MagicMock
from agentci.engineer import mint

def test_approve_and_mint_persists_when_proposed(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(mint, "_client", lambda: client)
    report = {"proposed_mint": {"id": "minted-refund-policy-0", "question": "q",
              "gold_resolution": "g", "policy_id": "refund-policy",
              "split": "tune", "source": "minted", "kb": "KB"}}
    out = mint.approve_and_mint(report)
    assert out["id"] == "minted-refund-policy-0"
    assert client.datasets.add_examples_to_dataset.called

def test_approve_and_mint_noop_when_absent(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(mint, "_client", lambda: client)
    assert mint.approve_and_mint({"proposed_mint": None}) is None
    assert not client.datasets.add_examples_to_dataset.called

def test_approve_persists_case_with_guard(monkeypatch):
    captured = {}
    monkeypatch.setattr(mint, "persist_minted_case", lambda case, ds=None: captured.setdefault("case", case))
    report = {"gate": "green", "proposed_mint": {"id": "minted-refund-0", "split": "tune",
              "guard": '{"kind":"assertion","slug":"refund-window"}'}}
    out = mint.approve_and_mint(report)
    assert out["id"] == "minted-refund-0"
    assert "guard" in captured["case"]
