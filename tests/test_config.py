from agentci import config

def test_thresholds_match_frozen_decisions():
    assert config.PASS_THRESHOLD == 0.7          # D9
    assert config.MIN_HELDOUT_LIFT == 0.05        # D8
    assert config.MAX_HELDOUT_REGRESSIONS == 0    # D8

def test_models_are_pinned_and_deterministic():
    assert config.TARGET_MODEL == "gemini-2.5-flash"   # D7 (original)
    assert config.ENGINEER_MODEL == "gemini-2.5-flash"   # D7 amendment 2026-06-08
    assert config.JUDGE_MODEL == "gemini-2.5-flash"      # D7 amendment 2026-06-08
    assert config.TEMPERATURE == 0.0             # D7

def test_baseline_prompt_is_registered():
    assert "refund" in config.BASELINE_SUPPORT_PROMPT.lower()

def test_improvement_judge_is_independent_family():
    from agentci import config
    # D17: the improvement ruler must NOT share a family with the optimizer.
    assert config.IMPROVEMENT_JUDGE_MODEL != config.ENGINEER_MODEL
    assert not config.IMPROVEMENT_JUDGE_MODEL.startswith("gemini")
    assert not config.GUARD_REVIEWER_MODEL.startswith("gemini")

def test_failure_taxonomy_is_fixed_set():
    from agentci import config
    assert "factual_omission" in config.FAILURE_TAXONOMY
    assert "over_refusal" in config.FAILURE_TAXONOMY
    assert len(config.FAILURE_TAXONOMY) == 5
