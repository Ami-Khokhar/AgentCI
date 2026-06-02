"""Agentic diagnosis (D11/D15/D19): a Gemini reason-act loop over Phoenix MCP that root-causes
the regression, classifies it into the fixed taxonomy, and AUTHORS a guard. It does NOT write the
fix (that is a separate agent, D19). Cached (D7) so the demo replays the captured trajectory."""
import asyncio
import json
import uuid

from agentci import cache, config

_DIAGNOSIS_GOAL = """The AgentCI regression gate is RED for candidate '{label}'.
These tune-set cases flipped PASS->FAIL versus baseline: {pass_to_fail}.

Investigate WHY, like a reliability engineer. Use your Phoenix MCP tools to pull the candidate
experiment ('cand-{label}-tune'), the baseline ('baseline-tune'), and per-case annotations/traces
for the flipped cases. Form a hypothesis, verify it holds across the flipped cases and is absent
from still-passing ones, and refine.

Classify the root cause into EXACTLY ONE category from: {taxonomy}.

CANDIDATE SYSTEM PROMPT (the edit under test — inspect it for what changed):
{candidate_prompt}

Then AUTHOR A GUARD — a regression test that asserts the specific property a correct answer must
satisfy. Prefer a deterministic 'assertion' when the property is crisp (a required phrase, a cited
policy id, a number); use a scoped 'rubric' (a one-line PASS/FAIL LLM-judge prompt) when the
property is semantic. The guard must be specific to THIS failure, not generic.

Also surface the single most telling flipped case as a side-by-side (question, baseline correct
answer, candidate wrong answer), pulled from traces via MCP.

Return ONLY JSON:
{{"hypothesis":"<...>",
  "investigation_steps":["<each MCP query/check, in order>"],
  "root_cause":{{"label":"<short>","policy_id":"<kb id>","category":"<one taxonomy value>","summary":"<one sentence>","case_ids":["..."]}},
  "headline_example":{{"id":"<case id>","question":"<ticket>","baseline_answer":"<correct>","candidate_answer":"<wrong>"}},
  "guard":{{"kind":"assertion|rubric","slug":"<kebab>","claim":"<property a correct answer must satisfy>","check":{{"type":"must_include|must_cite_policy|regex","values":["..."],"mode":"all|any","policy_id":"<id>","pattern":"<re>"}},"rubric_prompt":"<only if kind=rubric>","origin":{{"label":"<>","policy_id":"<>","category":"<>","case_ids":["..."]}}}}}}"""


def _parse_json(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_diagnosis(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> tuple[str, int]:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_engineer_agent

    runner = InMemoryRunner(agent=build_engineer_agent(), app_name="agentci-diagnose")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(app_name="agentci-diagnose", user_id=uid, session_id=sid)
    goal = _DIAGNOSIS_GOAL.format(
        label=label, pass_to_fail=pass_to_fail,
        taxonomy=", ".join(config.FAILURE_TAXONOMY),
        candidate_prompt=candidate_prompt,
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


def diagnose(candidate_prompt: str, label: str, pass_to_fail: list[str]) -> dict:
    """Root cause + taxonomy + headline + authored guard. No fix (D19). Cached (D7)."""
    payload = {"candidate_prompt": candidate_prompt, "label": label, "pass_to_fail": sorted(pass_to_fail)}

    def live():
        raw, mcp_calls = asyncio.run(_run_diagnosis(candidate_prompt, label, pass_to_fail))
        data = _parse_json(raw)
        data["mcp_calls"] = mcp_calls
        return data

    return cache.cached("diagnosis", payload, live)
