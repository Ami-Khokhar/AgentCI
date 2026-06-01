"""LLM-as-judge evaluators (D6): correctness, groundedness, completeness, policy_reference."""
import json
import re

from google import genai

from agentci import cache, config

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_judge_response(raw: str) -> dict:
    """Parse a judge response into {"score": float in [0,1], "explanation": str}."""
    text = raw.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        score = float(data.get("score", 0.0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"score": 0.0, "explanation": f"unparseable judge output: {raw[:120]}"}
    score = max(0.0, min(1.0, score))
    return {"score": score, "explanation": str(data.get("explanation", ""))}
