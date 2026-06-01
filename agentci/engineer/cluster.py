"""Cluster the regressed cases into one dominant failure pattern (LLM-as-analyst)."""
import json

from google import genai

from agentci import cache, config


def cluster_failures(cases: list[dict]) -> dict | None:
    """Return the dominant failure cluster for the given failing cases, or None if empty.

    Each case: {"id","question","gold","answer"}.
    Returns: {"label","policy_id","summary","case_ids"}.
    """
    if not cases:
        return None
    payload = {"cases": cases}

    def live():
        client = genai.Client()
        prompt = (
            "These support cases regressed (candidate answer is wrong vs gold). "
            "Identify the SINGLE dominant failure cluster.\n\n"
            f"{json.dumps(cases, indent=2)}\n\n"
            'Return ONLY JSON: {"label": "<short>", "policy_id": "<kb id>", '
            '"summary": "<one sentence>", "case_ids": ["..."]}'
        )
        resp = client.models.generate_content(
            model=config.ENGINEER_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    return cache.cached("cluster", payload, live)
