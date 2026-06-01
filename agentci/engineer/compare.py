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
import uuid as _uuid

from agentci import cache


async def _ask_engineer_for_baseline(experiment_name: str) -> str:
    """Drive the Engineer agent to fetch baseline per-case scores via Phoenix MCP."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-engineer")
    uid, sid = "agentci", _uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-engineer", user_id=uid, session_id=sid
    )
    prompt = (
        f"Using the Phoenix MCP tools, fetch experiment '{experiment_name}'. For each example "
        f"return its metadata id, split, the four annotation scores "
        f"(correctness, groundedness, completeness, policy_reference), and whether it passed "
        f"(all four >= {0.7}). Return ONLY a JSON array of objects with keys "
        f'"id","split","passed","scores".'
    )
    final = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def fetch_baseline_via_mcp(experiment_name: str) -> list[dict]:
    """Return baseline per-case rows, read at runtime THROUGH Phoenix MCP (GAP-4). Cached (D7)."""
    payload = {"experiment_name": experiment_name}

    def live():
        raw = asyncio.run(_ask_engineer_for_baseline(experiment_name))
        text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return _json.loads(text)

    return cache.cached("mcp_baseline", payload, live)
