from agentci.target import kb

def test_lookup_kb_returns_matching_section():
    result = kb.lookup_kb("refund window")
    assert result["status"] == "success"
    assert any("refund" in s["title"].lower() for s in result["sections"])

def test_lookup_kb_unknown_returns_empty_success():
    result = kb.lookup_kb("how to fly to the moon")
    assert result["status"] == "success"
    assert result["sections"] == []
