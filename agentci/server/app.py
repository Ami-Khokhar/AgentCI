"""FastAPI dashboard: serves run reports and the approve (mint) action (D12/D14)."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from agentci.engineer.mint import approve_and_mint

_RUNS_DIR = Path("runs")
_STATIC = Path(__file__).resolve().parent / "static"


def _load_report(label: str) -> dict:
    p = _RUNS_DIR / f"{label}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no run report for {label!r}")
    return json.loads(p.read_text(encoding="utf-8"))


def create_app() -> FastAPI:
    app = FastAPI(title="AgentCI")

    @app.get("/api/runs")
    def list_runs():
        return sorted(p.stem for p in _RUNS_DIR.glob("*.json")) if _RUNS_DIR.exists() else []

    @app.get("/api/report/{label}")
    def get_report(label: str):
        return _load_report(label)

    @app.post("/api/approve/{label}")
    def approve(label: str):
        report = _load_report(label)
        if report.get("gate") != "green" or not report.get("proposed_mint"):
            raise HTTPException(status_code=409, detail="nothing to approve (gate not green / no proposed mint)")
        minted = approve_and_mint(report)
        report["minted"] = minted
        (_RUNS_DIR / f"{label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"approved": True, "minted": minted}

    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
    return app


app = create_app()
