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
    _seed(tmp_path, "reg", {"gate": "green", "proposed_mint": {"id": "m"}})
    monkeypatch.setattr(appmod, "approve_and_mint", lambda report: {"id": "m"})
    c = TestClient(appmod.create_app())
    r = c.post("/api/approve/reg")
    assert r.status_code == 200 and r.json()["approved"] is True and r.json()["minted"] == {"id": "m"}

def test_approve_red_is_409(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path, "reg", {"gate": "red", "proposed_mint": None})
    c = TestClient(appmod.create_app())
    assert c.post("/api/approve/reg").status_code == 409
