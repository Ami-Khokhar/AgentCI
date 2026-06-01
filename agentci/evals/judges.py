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


_RUBRICS = {
    "correctness": "Does the ANSWER match the GOLD resolution in substance? "
                   "1.0 = fully correct, 0.0 = wrong or contradictory.",
    "groundedness": "Is every claim in the ANSWER supported by the KNOWLEDGE BASE? "
                    "Penalize any invented policy. 1.0 = fully grounded, 0.0 = hallucinated.",
    "completeness": "Does the ANSWER fully resolve the request (or correctly route it), "
                    "covering all conditions the GOLD resolution covers? 1.0 = complete.",
    "policy_reference": "Does the ANSWER cite/reference the correct policy section "
                        "(expected policy id given)? 1.0 = correct citation, 0.0 = none/wrong.",
}


def _judge(dimension: str, output: dict, expected: dict, metadata: dict) -> float:
    answer = (output or {}).get("answer", "")
    gold = (expected or {}).get("gold_resolution", "")
    kb = (metadata or {}).get("kb", "")
    payload = {"dimension": dimension, "output": answer, "expected": gold, "kb": kb}

    def live():
        client = genai.Client()
        prompt = (
            f"You are a strict evaluator. RUBRIC: {_RUBRICS[dimension]}\n\n"
            f"KNOWLEDGE BASE:\n{kb}\n\nGOLD RESOLUTION:\n{gold}\n\n"
            f"EXPECTED POLICY ID: {(metadata or {}).get('policy_id','')}\n\n"
            f"ANSWER UNDER TEST:\n{answer}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>, "explanation": "<one sentence>"}'
        )
        resp = client.models.generate_content(
            model=config.JUDGE_MODEL,
            contents=prompt,
            config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
        )
        return parse_judge_response(resp.text)

    return cache.cached("judge", payload, live)["score"]


def correctness(output, expected, metadata) -> float:
    return _judge("correctness", output, expected, metadata)


def groundedness(output, expected, metadata) -> float:
    return _judge("groundedness", output, expected, metadata)


def completeness(output, expected, metadata) -> float:
    return _judge("completeness", output, expected, metadata)


def policy_reference(output, expected, metadata) -> float:
    return _judge("policy_reference", output, expected, metadata)


ALL_EVALUATORS = [correctness, groundedness, completeness, policy_reference]
