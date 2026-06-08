"""Compare candidate vs baseline per-case results. Baseline is fetched THROUGH Phoenix MCP."""


def _index(rows: list[dict]) -> dict:
    return {r["id"]: r for r in rows}


def compute_flips(baseline: list[dict], candidate: list[dict]) -> dict:
    """Return {'pass_to_fail': [ids], 'fail_to_pass': [ids]} over ids present in both."""
    b, c = _index(baseline), _index(candidate)
    ptf, ftp = [], []
    for cid in sorted(b.keys() & c.keys()):
        if b[cid]["passed"] and not c[cid]["passed"]:
            ptf.append(cid)
        elif not b[cid]["passed"] and c[cid]["passed"]:
            ftp.append(cid)
    return {"pass_to_fail": ptf, "fail_to_pass": ftp}


def is_regression(baseline: list[dict], candidate: list[dict]) -> bool:
    """A candidate is flagged iff >=1 TUNE-partition pass->fail flip (D10)."""
    tune_base = [r for r in baseline if r["split"] == "tune"]
    tune_cand = [r for r in candidate if r["split"] == "tune"]
    return len(compute_flips(tune_base, tune_cand)["pass_to_fail"]) > 0


import asyncio
import json as _json

from agentci import cache


async def _get_experiment_by_id_via_mcp(experiment_id: str) -> dict:
    """Call the Phoenix MCP server's get-experiment-by-id over stdio and return the parsed payload.

    Done as a direct, deterministic MCP tool call (not an LLM agent): the experiment holds 160
    judge scores and an agent transcribing them is both unreliable and burns quota. The agentic
    reason-act loop lives in diagnose() — this is plumbing that must be exact.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from agentci.engineer.agent import phoenix_mcp_server_params

    async with stdio_client(phoenix_mcp_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get-experiment-by-id", {"experiment_id": experiment_id})
            if getattr(result, "isError", False):
                raise RuntimeError(f"phoenix-mcp get-experiment-by-id failed: {result.content[0].text[:200]}")
            return _json.loads(result.content[0].text)


def _dataset_example_meta() -> dict:
    """Map Phoenix dataset_example_id -> example metadata ({'id': 't05', 'split': 'tune', ...})."""
    from phoenix.client import Client
    from agentci import config
    ds = Client().datasets.get_dataset(dataset=config.DATASET_NAME)
    return {ex["id"]: ex.get("metadata", {}) for ex in ds.examples}


def fetch_baseline_via_mcp(experiment_name: str) -> list[dict]:
    """Return baseline per-case rows, read at runtime THROUGH Phoenix MCP (GAP-4). Cached (D7).

    Phoenix stores experiments anonymously, so we resolve the logical name -> experiment id via the
    registry (populated by run_candidate) and fetch it BY ID through the MCP server. The 4 judge
    annotation scores come from the experiment; id/split come from the dataset example metadata.
    """
    from agentci import config, experiments_registry

    payload = {"experiment_name": experiment_name}
    dims = config.RUBRIC_DIMENSIONS
    threshold = config.PASS_THRESHOLD

    def live():
        experiment_id = experiments_registry.get_id(experiment_name)
        data = asyncio.run(_get_experiment_by_id_via_mcp(experiment_id))
        runs = data.get("experimentResult") or data.get("experiment_result") or []
        meta_by_example = _dataset_example_meta()
        rows = []
        for run in runs:
            md = meta_by_example.get(run.get("example_id"), {})
            scores = {a["name"]: float(a.get("score") or 0.0)
                      for a in (run.get("annotations") or []) if a.get("name") in dims}
            scores = {dim: scores.get(dim, 0.0) for dim in dims}
            rows.append({
                "id": md.get("id"),
                "split": md.get("split"),
                "passed": all(scores[dim] >= threshold for dim in dims),
                "scores": scores,
                "answer": (run.get("output") or {}).get("answer", "") if isinstance(run.get("output"), dict) else "",
            })
        return rows

    return cache.cached("mcp_baseline", payload, live)
