"""Fix-authoring agent (D19): a separate Gemini agent that, given the root cause, writes ONE
corrective edit to the candidate prompt — kept apart from diagnosis so neither task degrades the
other. Cached (D7)."""
import asyncio
import json
import uuid

from agentci import cache

_FIX_GOAL = """A regression was root-caused in candidate prompt below.

ROOT CAUSE: {root_cause}

CANDIDATE SYSTEM PROMPT:
{candidate_prompt}

Propose ONE corrective edit to the candidate prompt that fixes this root cause while preserving the
candidate's intent (e.g. brevity). Do not over-correct unrelated behaviour.

Return ONLY JSON: {{"revised_prompt":"<full new prompt>","rationale":"<why>"}}"""


def _parse_json(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_fix(candidate_prompt: str, root_cause: dict) -> str:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_fix_agent

    runner = InMemoryRunner(agent=build_fix_agent(), app_name="agentci-fix")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(app_name="agentci-fix", user_id=uid, session_id=sid)
    goal = _FIX_GOAL.format(candidate_prompt=candidate_prompt, root_cause=json.dumps(root_cause))
    final = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=goal)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def author_fix(candidate_prompt: str, root_cause: dict) -> dict:
    """Propose {revised_prompt, rationale} for the root cause (D19). Cached (D7)."""
    payload = {"candidate_prompt": candidate_prompt, "root_cause": root_cause}

    def live():
        from agentci import throttle
        return _parse_json(throttle.call_with_backoff(lambda: asyncio.run(_run_fix(candidate_prompt, root_cause))))

    return cache.cached("fix", payload, live)
