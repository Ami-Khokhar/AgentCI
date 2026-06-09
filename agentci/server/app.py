"""FastAPI dashboard: serves run reports and the approve (mint) action (D12/D14)."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from agentci.engineer.mint import approve_and_mint
from datetime import datetime, timezone

from agentci.memory import memory

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
        if report.get("minted"):
            raise HTTPException(status_code=409, detail="already approved — nothing to do")
        minted = approve_and_mint(report)
        entry = memory.record_approval(report, datetime.now(timezone.utc).isoformat())
        report["minted"] = minted
        report["memory_entry"] = entry
        (_RUNS_DIR / f"{label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"approved": True, "minted": minted, "memory_entry": entry}

    @app.get("/api/memory")
    def get_memory():
        return list(reversed(memory.load_memory()))

    @app.get("/api/meta")
    def get_meta():
        """Provenance for the 'recorded live' badge — the models/provider behind a real run."""
        import os
        from agentci import config
        if os.environ.get("AGENTCI_RULER") == "gemini":
            ruler = f"{config.RULER_GEMINI_MODEL} (same-family fallback)"
        elif os.environ.get("ANTHROPIC_USE_VERTEX") == "true":
            ruler = f"{config.RULER_VERTEX_MODEL} on Vertex"
        elif os.environ.get("GROQ_API_KEY"):
            ruler = config.FREE_RULER_MODEL
        else:
            ruler = config.IMPROVEMENT_JUDGE_MODEL
        provider = "Vertex AI" if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "true" else "AI Studio"
        return {
            "target_model": config.TARGET_MODEL,
            "engineer_model": config.ENGINEER_MODEL,
            "judge_model": config.JUDGE_MODEL,
            "ruler": ruler,
            "provider": provider,
            "phoenix_project": os.environ.get("PHOENIX_PROJECT_NAME", "agentci"),
        }

    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
    return app


app = create_app()
