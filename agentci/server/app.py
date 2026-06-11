"""FastAPI dashboard: serves run reports and the approve (mint) action (D12/D14)."""
import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from agentci.engineer.mint import approve_and_mint
from datetime import datetime, timezone

from agentci.memory import memory

_RUNS_DIR = Path("runs")
_CANDIDATES_DIR = Path("candidates")
_STATIC = Path(__file__).resolve().parent / "static"

# Live-investigation jobs, keyed by run label. The investigator is the one part of the pipeline
# we run LIVE on the hosted demo: a real Gemini reason-act loop over the Phoenix MCP server, on the
# already-detected regression. It is a handful of model+MCP calls (~1-4 min) — not the 250-call full
# pipeline, which a fresh-project Vertex quota cannot serve in a request. One Cloud Run instance
# (--max-instances 1) so this dict is process-consistent.
_INVESTIGATIONS: dict[str, dict] = {}
_INVESTIGATION_LOCK = threading.Lock()


def _load_report(label: str) -> dict:
    p = _RUNS_DIR / f"{label}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no run report for {label!r}")
    return json.loads(p.read_text(encoding="utf-8"))


def _investigable_runs() -> list[str]:
    """Labels whose live investigator can run: candidate prompt bundled, tune experiment registered,
    AND the run actually has a regression (a benign run has nothing to investigate)."""
    from agentci import experiments_registry
    out = []
    if not _CANDIDATES_DIR.exists():
        return out
    for cand in _CANDIDATES_DIR.glob("*.txt"):
        label = cand.stem
        try:
            experiments_registry.get_id(f"cand-{label}-tune")
        except KeyError:
            continue
        report_path = _RUNS_DIR / f"{label}.json"
        if not report_path.exists():
            continue
        try:
            if json.loads(report_path.read_text(encoding="utf-8")).get("regression_detected"):
                out.append(label)
        except (ValueError, OSError):
            continue
    return sorted(out)


def _run_investigation(label: str, candidate_prompt: str, pass_to_fail: list[str]) -> None:
    """Background worker: run the real investigator and stash the result. AGENTCI_CACHE_MODE=live
    on the deployed app makes every call genuinely live (no cache read/write)."""
    job = _INVESTIGATIONS[label]
    try:
        from agentci.tracing import init_tracing
        init_tracing()
        from agentci.engineer.diagnose import diagnose
        result = diagnose(candidate_prompt, label, pass_to_fail)
        with _INVESTIGATION_LOCK:
            job["result"] = result
            job["state"] = "done"
    except Exception as e:  # surface the real failure to the page rather than a blank spinner
        with _INVESTIGATION_LOCK:
            job["error"] = f"{type(e).__name__}: {e}"
            job["state"] = "error"


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

    @app.post("/api/investigate/{label}")
    def start_investigation(label: str):
        """Kick off a LIVE investigator run for an already-detected regression (D11). Returns
        immediately; the page polls /status. Re-running is allowed (each click is genuinely live)."""
        report = _load_report(label)
        if not report.get("regression_detected"):
            raise HTTPException(status_code=409, detail="no regression to investigate for this run")
        cand_path = _CANDIDATES_DIR / f"{label}.txt"
        if not cand_path.exists():
            raise HTTPException(status_code=404, detail=f"candidate prompt {cand_path.name} not bundled")
        prompt = cand_path.read_text(encoding="utf-8").strip()
        pass_to_fail = report.get("flips", {}).get("pass_to_fail", [])
        with _INVESTIGATION_LOCK:
            if _INVESTIGATIONS.get(label, {}).get("state") == "running":
                return {"state": "running"}  # idempotent: don't spawn a second live run
            _INVESTIGATIONS[label] = {"state": "running", "started": time.time(),
                                      "result": None, "error": None}
        threading.Thread(target=_run_investigation, args=(label, prompt, pass_to_fail),
                         daemon=True).start()
        return {"state": "running"}

    @app.get("/api/investigate/{label}/status")
    def investigation_status(label: str):
        job = _INVESTIGATIONS.get(label)
        if not job:
            return {"state": "idle"}
        with _INVESTIGATION_LOCK:
            out = {"state": job["state"], "elapsed": round(time.time() - job["started"])}
            if job["state"] == "done":
                out["result"] = job["result"]
            elif job["state"] == "error":
                out["error"] = job["error"]
        return out

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
            # Runs the live investigator can actually run: candidate prompt bundled AND its tune
            # experiment id is registered (so diagnose can pull it through Phoenix MCP). Lets the
            # dashboard show the "Run live" button only where it will work.
            "investigable_runs": _investigable_runs(),
        }

    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
    return app


app = create_app()
