"""Fix-authoring agent (D19): a separate Gemini agent that, given the root cause, writes ONE
corrective edit to the candidate prompt — kept apart from diagnosis so neither task degrades the
other. Cached (D7)."""
import asyncio
import json
import uuid

from agentci import cache

_FIX_GOAL = """A regression was root-caused in candidate prompt below.

ROOT CAUSE: {root_cause}

PRODUCTION BASELINE SYSTEM PROMPT (the behaviour your fix must recover):
{baseline_prompt}

CANDIDATE SYSTEM PROMPT (the regressed change):
{candidate_prompt}

Propose ONE corrective edit to the candidate prompt. The fix is judged as a RECOVERY: on held-out
tickets it must perform at least as well as the baseline. Restore every baseline behaviour the
candidate dropped (KB-only grounding, exact policy citations, human routing, refund specifics);
keep whatever candidate intent does not conflict with those. If an intent (e.g. brevity) caused
the regression, correctness wins. Do not over-correct unrelated behaviour.

Answers are evaluated on four dimensions: correctness against a gold resolution, groundedness
(claims supported by the KB only), completeness (fully resolve the request — apply the policy to
the customer's specific situation and cover every condition that applies, not just the general
rule), and exact policy citation. Your revised prompt must elicit answers that satisfy all four.

Return ONLY JSON: {{"revised_prompt":"<full new prompt>","rationale":"<why>"}}"""


def _parse_json(raw: str) -> dict:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


async def _run_fix(goal: str) -> str:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from agentci.engineer.agent import build_fix_agent

    runner = InMemoryRunner(agent=build_fix_agent(), app_name="agentci-fix")
    uid, sid = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(app_name="agentci-fix", user_id=uid, session_id=sid)
    final = ""
    async for event in runner.run_async(
        user_id=uid, session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=goal)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def author_fix(candidate_prompt: str, root_cause: dict, baseline_prompt: str) -> dict:
    """Propose {revised_prompt, rationale} for the root cause (D19). The rendered goal IS the
    model input, so it is the cache payload — any change to the goal template, the baseline
    prompt (the recovery bar, D8), or the root cause re-keys the recording. Cached (D7)."""
    goal = _FIX_GOAL.format(candidate_prompt=candidate_prompt, root_cause=json.dumps(root_cause),
                            baseline_prompt=baseline_prompt)
    payload = {"goal": goal}

    def live():
        from agentci import throttle
        return _parse_json(throttle.call_with_backoff(lambda: asyncio.run(_run_fix(goal))))

    return cache.cached("fix", payload, live)
