from agentci.evals import experiment

def test_passed_requires_all_dims_above_threshold():
    scores = {"correctness": 0.9, "groundedness": 0.8, "completeness": 0.75, "policy_reference": 0.7}
    assert experiment.case_passed(scores) is True
    scores["policy_reference"] = 0.69
    assert experiment.case_passed(scores) is False

def test_normalize_results_shapes_rows():
    raw = [
        {"id": "t00", "split": "tune",
         "scores": {"correctness": 0.9, "groundedness": 0.9, "completeness": 0.9, "policy_reference": 0.9}},
        {"id": "t01", "split": "held_out",
         "scores": {"correctness": 0.2, "groundedness": 0.9, "completeness": 0.9, "policy_reference": 0.9}},
    ]
    rows = experiment.normalize_results(raw)
    assert rows[0]["passed"] is True
    assert rows[1]["passed"] is False
    assert rows[1]["split"] == "held_out"
