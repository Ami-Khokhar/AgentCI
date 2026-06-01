from agentci.evals.judges import parse_judge_response

def test_parses_plain_json():
    out = parse_judge_response('{"score": 0.8, "explanation": "good"}')
    assert out == {"score": 0.8, "explanation": "good"}

def test_strips_code_fence_and_clamps():
    raw = "```json\n{\"score\": 1.4, \"explanation\": \"over\"}\n```"
    out = parse_judge_response(raw)
    assert out["score"] == 1.0

def test_missing_score_defaults_to_zero():
    out = parse_judge_response("not json at all")
    assert out["score"] == 0.0
    assert "explanation" in out
