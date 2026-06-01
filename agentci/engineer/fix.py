"""Draft a revised system prompt targeting the failure cluster, preserving candidate intent."""
import json

from google import genai

from agentci import cache, config


def draft_fix(candidate_prompt: str, cluster: dict) -> dict:
    """Return {"revised_prompt", "rationale"} fixing `cluster` while keeping candidate intent."""
    payload = {"candidate_prompt": candidate_prompt, "cluster": cluster}

    def live():
        client = genai.Client()
        prompt = (
            "A candidate support-agent system prompt caused a regression cluster. "
            "Revise the prompt to FIX the cluster while preserving the candidate's intent "
            "(e.g. brevity/token savings). Do not over-correct other behaviors.\n\n"
            f"CANDIDATE PROMPT:\n{candidate_prompt}\n\n"
            f"FAILURE CLUSTER:\n{json.dumps(cluster, indent=2)}\n\n"
            'Return ONLY JSON: {"revised_prompt": "<full new prompt>", "rationale": "<why>"}'
        )
        resp = client.models.generate_content(
            model=config.ENGINEER_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    return cache.cached("fix", payload, live)
