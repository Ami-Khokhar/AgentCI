"""Cross-family judge (D17): a non-Gemini model scores held-out correctness and rubric guards,
so the ruler never shares a brain with the Gemini investigator/fix-author. Cached (D7)."""
import json

from agentci import cache, config


def _anthropic_json(prompt: str, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model, max_tokens=512, temperature=config.TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def judge_correctness(answer: str, gold: str) -> float:
    """Independent-family correctness score in [0,1] for held-out lift (D17). Cached."""
    payload = {"answer": answer, "gold": gold}

    def live():
        prompt = (
            "You are a strict, independent evaluator. Score how well the ANSWER matches the "
            "GOLD resolution in substance: 1.0 = fully correct, 0.0 = wrong or contradictory.\n\n"
            f"GOLD:\n{gold}\n\nANSWER:\n{answer}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>}'
        )
        data = _anthropic_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
        return {"score": max(0.0, min(1.0, float(data.get("score", 0.0))))}

    return cache.cached("independent_judge", payload, live)["score"]


def score_rubric_guard(guard: dict, answer: str) -> dict:
    """Score a rubric guard against an answer on the independent family. Cached."""
    payload = {"slug": guard["slug"], "rubric_prompt": guard["rubric_prompt"], "answer": answer}

    def live():
        prompt = (
            "You are a strict guard. Apply this PASS/FAIL rubric to the ANSWER.\n\n"
            f"RUBRIC: {guard['rubric_prompt']}\n\nANSWER:\n{answer}\n\n"
            'Return ONLY JSON: {"passed": <true|false>, "detail": "<one sentence>"}'
        )
        data = _anthropic_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
        return {"passed": bool(data.get("passed", False)), "detail": str(data.get("detail", ""))}

    return cache.cached("guard_judge", payload, live)
