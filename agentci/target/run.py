"""Callable entrypoint for the support agent: (prompt, ticket) -> {"answer": ...}."""
import asyncio
import uuid

from google.adk.runners import InMemoryRunner
from google.genai import types

from agentci import cache, config, throttle
from agentci.target.agent import build_support_agent


async def _run_once(system_prompt: str, ticket: str) -> str:
    agent = build_support_agent(system_prompt)
    runner = InMemoryRunner(agent=agent, app_name="agentci-target")
    user_id, session_id = "agentci", uuid.uuid4().hex
    await runner.session_service.create_session(
        app_name="agentci-target", user_id=user_id, session_id=session_id
    )
    final = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=ticket)]),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def answer_ticket(prompt: str, ticket: str) -> dict:
    """Run the support agent on one ticket. Cached for determinism (D7). The live call is paced
    + retried on 429 via the shared Gemini rate gate (the ADK runner bursts otherwise)."""
    payload = {"prompt": prompt, "ticket": ticket}

    def live():
        return {"answer": throttle.call_with_backoff(lambda: asyncio.run(_run_once(prompt, ticket)))}

    return cache.cached("target", payload, live)
