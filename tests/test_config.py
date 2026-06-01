from agentci import config

def test_thresholds_match_frozen_decisions():
    assert config.PASS_THRESHOLD == 0.7          # D9
    assert config.MIN_HELDOUT_LIFT == 0.05        # D8
    assert config.MAX_HELDOUT_REGRESSIONS == 0    # D8

def test_models_are_pinned_and_deterministic():
    assert config.TARGET_MODEL == "gemini-2.5-flash"
    assert config.ENGINEER_MODEL == "gemini-2.5-pro"
    assert config.JUDGE_MODEL == "gemini-2.5-pro"
    assert config.TEMPERATURE == 0.0             # D7

def test_baseline_prompt_is_registered():
    assert "refund" in config.BASELINE_SUPPORT_PROMPT.lower()
