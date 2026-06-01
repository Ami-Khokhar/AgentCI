import json
from agentci import cache

def test_record_then_replay_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "record")
    calls = {"n": 0}

    def live():
        calls["n"] += 1
        return {"text": "hello"}

    out1 = cache.cached("judge", {"q": 1}, live)
    assert out1 == {"text": "hello"}
    assert calls["n"] == 1

    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    out2 = cache.cached("judge", {"q": 1}, live)
    assert out2 == {"text": "hello"}
    assert calls["n"] == 1  # unchanged

def test_replay_miss_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTCI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTCI_CACHE_MODE", "replay")
    try:
        cache.cached("judge", {"q": 999}, lambda: {"text": "x"})
        assert False, "expected CacheMissError"
    except cache.CacheMissError:
        pass
