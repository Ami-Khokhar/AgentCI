import json
from pathlib import Path
from agentci import cache
from agentci.target import run


def test_answer_ticket_replays_cached_response(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    # Pre-seed a recording under the exact key answer_ticket will compute.
    key_payload = {"prompt": "P", "ticket": "How do refunds work?"}
    digest_path = tmp_path / (cache._key("target", key_payload) + ".json")
    digest_path.write_text(json.dumps({"answer": "Refunds within 14 days."}))

    out = run.answer_ticket("P", "How do refunds work?")
    assert out == {"answer": "Refunds within 14 days."}
