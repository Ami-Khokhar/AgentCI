import json
from pathlib import Path

from fastapi.testclient import TestClient

from agentci.server import app as appmod

def _seed(tmp_path, label, report):
    (tmp_path / "runs").mkdir(exist_ok=True)
    (tmp_path / "runs" / f"{label}.json").write_text(json.dumps(report), encoding="utf-8")

def test_get_report_and_404(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "reg", {"gate": "green", "verdict": "green_promotable_fix",
                            "proposed_mint": {"id": "m"}})
    c = TestClient(appmod.create_app())
    r = c.get("/api/report/reg")
    assert r.status_code == 200 and r.json()["gate"] == "green"
    assert c.get("/api/report/missing").status_code == 404

def test_list_runs(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "reg", {"gate": "green"})
    _seed(tmp_path, "benign", {"gate": "green"})
    c = TestClient(appmod.create_app())
    assert set(c.get("/api/runs").json()) == {"reg", "benign"}

def test_approve_green_calls_mint(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    _seed(tmp_path, "reg", {"gate": "green", "proposed_mint": {"id": "m"}})
    monkeypatch.setattr(appmod, "approve_and_mint", lambda report, dataset_name=None: {"id": "m"})
    c = TestClient(appmod.create_app())
    r = c.post("/api/approve/reg")
    assert r.status_code == 200 and r.json()["approved"] is True and r.json()["minted"] == {"id": "m"}

def test_approve_red_is_409(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "reg", {"gate": "red", "proposed_mint": None})
    c = TestClient(appmod.create_app())
    assert c.post("/api/approve/reg").status_code == 409


def test_approve_writes_memory_entry(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    report = {"candidate_label": "reg-concise", "gate": "green",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "always cite refund policy"},
              "proposed_mint": {"id": "minted-refund-policy-0", "guard": '{"slug": "refund-window"}'}}
    _seed(tmp_path, "reg-concise", report)
    monkeypatch.setattr(appmod, "approve_and_mint", lambda report, dataset_name=None: report["proposed_mint"])
    c = TestClient(appmod.create_app())
    r = c.post("/api/approve/reg-concise")
    assert r.status_code == 200
    assert r.json()["memory_entry"]["failure_type"] == "factual_omission"
    persisted = json.loads((tmp_path / "runs" / "reg-concise.json").read_text())
    assert persisted["memory_entry"]["failure_type"] == "factual_omission"
    from agentci.memory import memory
    assert len(memory.load_memory()) == 1


def test_approve_already_approved_is_409(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    _seed(tmp_path, "reg", {"gate": "green", "proposed_mint": {"id": "m"}, "minted": {"id": "m"}})
    c = TestClient(appmod.create_app())
    assert c.post("/api/approve/reg").status_code == 409


def test_get_memory_endpoint_newest_first(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    from agentci.memory import memory
    memory.append_entry({"failure_type": "a", "lesson": "first"})
    memory.append_entry({"failure_type": "b", "lesson": "second"})
    c = TestClient(appmod.create_app())
    out = c.get("/api/memory").json()
    assert [e["lesson"] for e in out] == ["second", "first"]
