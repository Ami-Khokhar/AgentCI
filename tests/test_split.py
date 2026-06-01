from agentci.data.dataset import assign_splits

def test_60_40_split_is_deterministic_and_ordered():
    tickets = [{"id": f"t{i:02d}"} for i in range(40)]
    out = assign_splits(tickets)
    tune = [t for t in out if t["split"] == "tune"]
    held = [t for t in out if t["split"] == "held_out"]
    assert len(tune) == 24 and len(held) == 16        # D3
    assert tune[0]["id"] == "t00" and held[0]["id"] == "t24"
    # source defaults to "seed"
    assert all(t["source"] == "seed" for t in out)

def test_split_rounds_down_tune_for_small_sets():
    tickets = [{"id": f"t{i}"} for i in range(10)]
    out = assign_splits(tickets)
    assert sum(t["split"] == "tune" for t in out) == 6
