"""Agentic regression investigator (D11): a Gemini reason-act loop over Phoenix MCP.

When the gate is red, this drives the Engineer LlmAgent (which mounts the Phoenix MCP
toolset) with an open-ended GOAL, not a script. The agent decides which experiments/traces
to query through MCP, forms and checks a hypothesis, and returns a structured root-cause +
proposed fix. The whole run (including the real MCP tool-call count) is cached (D7), so the
demo replays the captured trajectory deterministically.
"""
import asyncio
import json
import uuid

from agentci import cache

_INVESTIGATION_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped from PASS to FAIL versus the baseline: {pass_to_fail}.

Investigate WHY, like a reliability engineer. Use your Phoenix MCP tools to pull the
candidate experiment ('cand-{label}-tune'), the baseline experiment ('baseline-tune'),
and the per-case annotations/traces for the flipped cases. Form a hypothesis about the
common failure pattern, verify it holds across the flipped cases (and is absent from
still-passing cases), and refine if needed. Then propose ONE corrective edit to the
candidate system prompt that fixes the cluster while preserving the candidate's intent
(e.g. brevity). Do not over-correct unrelated behaviour.

CANDIDATE SYSTEM PROMPT:
{candidate_prompt}

Also surface the single most telling flipped case as a side-by-side: its question, the
baseline's correct answer, and the candidate's (fluent but wrong) answer — the one a human
skimming a few outputs would likely have approved. Pull both answers from the traces via MCP.

Return ONLY JSON:
{{"hypothesis": "<initial hypothesis>",
  "investigation_steps": ["<each MCP query / check you ran, in order>"],
  "root_cause": {{"label":"<short>","policy_id":"<kb id>","summary":"<one sentence>","case_ids":["..."]}},
  "headline_example": {{"id":"<case id>","question":"<ticket>","baseline_answer":"<correct>","candidate_answer":"<wrong>"}},
  "proposed_fix": {{"revised_prompt":"<full new prompt>","rationale":"<why>"}}}}"""


def _parse_investigation(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_investigation(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> tuple[str, int]:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-investigator")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-investigator", user_id=uid, session_id=sid
    )
    goal = _INVESTIGATION_GOAL.format(
        label=label, pass_to_fail=pass_to_fail, candidate_prompt=candidate_prompt
    )
    final, mcp_calls = "", 0
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=goal)]),
    ):
        fcs = event.get_function_calls() if hasattr(event, "get_function_calls") else None
        if fcs:
            mcp_calls += len(fcs)
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final, mcp_calls


def investigate(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> dict:
    """Agentic root-cause + proposed fix via a Phoenix-MCP reason-act loop (D11). Cached (D7).

    Returns {"hypothesis","investigation_steps","root_cause","proposed_fix","mcp_calls"}.
    """
    payload = {"candidate_prompt": candidate_prompt, "label": label, "pass_to_fail": sorted(pass_to_fail)}

    def live():
        raw, mcp_calls = asyncio.run(_run_investigation(candidate_prompt, label, pass_to_fail))
        data = _parse_investigation(raw)
        data["mcp_calls"] = mcp_calls
        return data

    return cache.cached("investigation", payload, live)
