"""Adversarial rubric review (D18): an independent-family model judges whether a rubric guard is
specific, non-gameable, and not over-constrained. Only applies to kind='rubric'. Cached (D7)."""
from agentci import cache, config
from agentci.engineer.independent_judge import _independent_json


def review_rubric(guard: dict) -> dict:
    """Score a rubric guard's quality in [0,1]. Cached."""
    payload = {"slug": guard["slug"], "rubric_prompt": guard["rubric_prompt"]}

    def live():
        prompt = (
            "You review proposed regression-test rubrics. Score this rubric 0..1 on: is it "
            "SPECIFIC to one failure (not generic), is it NOT trivially gameable, and is it NOT "
            "over-constrained (would not reject a correct answer phrased differently). "
            "Low score if it fails any.\n\n"
            f"RUBRIC: {guard['rubric_prompt']}\n\n"
            'Return ONLY JSON: {"score": <float 0..1>, "notes": "<one sentence>"}'
        )
        data = _independent_json(prompt, config.GUARD_REVIEWER_MODEL)
        return {"score": max(0.0, min(1.0, float(data.get("score", 0.0)))),
                "notes": str(data.get("notes", ""))}

    return cache.cached("guard_review", payload, live)


def passes_review(review: dict) -> bool:
    return review.get("score", 0.0) >= config.GUARD_REVIEW_THRESHOLD
