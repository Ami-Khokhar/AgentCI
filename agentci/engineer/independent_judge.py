"""Cross-family judge (D17): a non-Gemini model scores held-out correctness and rubric guards,
so the ruler never shares a brain with the Gemini investigator/fix-author. Cached (D7)."""
import json

from agentci import cache, config


def _parse_fenced_json(text: str) -> dict:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def _anthropic_text_with_backoff(client, model: str, prompt: str) -> str:
    """messages.create with exponential backoff on 429 — the Vertex `global` endpoint shares a
    prediction quota with the Gemini experiments, so transient rate limits are expected."""
    import time
    import anthropic
    delay = 4.0
    for attempt in range(6):
        try:
            msg = client.messages.create(
                model=model, max_tokens=512, temperature=config.TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except anthropic.RateLimitError:
            if attempt == 5:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60.0)


def _independent_json(prompt: str, model: str) -> dict:
    """Call the independent-family ruler (D17). Provider is env-selected (all non-Gemini, so the
    ruler never shares a brain with the investigator/fix-author):
    - Claude on Vertex AI (billed to the GCP project) when ANTHROPIC_USE_VERTEX=true
    - a free Groq key (Llama) when GROQ_API_KEY is set
    - else the direct Anthropic API with `model`."""
    import os
    if os.environ.get("ANTHROPIC_USE_VERTEX") == "true":
        from anthropic import AnthropicVertex
        client = AnthropicVertex(
            project_id=os.environ["GOOGLE_CLOUD_PROJECT"],
            region=os.environ.get("ANTHROPIC_VERTEX_REGION", "global"),
        )
        return _parse_fenced_json(
            _anthropic_text_with_backoff(client, config.RULER_VERTEX_MODEL, prompt)
        )
    if os.environ.get("GROQ_API_KEY"):
        import httpx
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={"model": config.FREE_RULER_MODEL, "temperature": config.TEMPERATURE,
                  "max_tokens": 512,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60.0,
        )
        resp.raise_for_status()
        return _parse_fenced_json(resp.json()["choices"][0]["message"]["content"])
    import anthropic
    client = anthropic.Anthropic()
    return _parse_fenced_json(_anthropic_text_with_backoff(client, model, prompt))


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
        data = _independent_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
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
        data = _independent_json(prompt, config.IMPROVEMENT_JUDGE_MODEL)
        return {"passed": bool(data.get("passed", False)), "detail": str(data.get("detail", ""))}

    return cache.cached("guard_judge", payload, live)
