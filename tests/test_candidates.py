import json
from pathlib import Path

CAND = Path("candidates")

def test_labels_cover_six_with_correct_split():
    labels = json.loads((CAND / "labels.json").read_text())
    assert len(labels) == 6
    counts = {}
    for v in labels.values():
        counts[v] = counts.get(v, 0) + 1
    assert counts == {"regressive": 2, "benign": 2, "improving": 2}  # D4

def test_every_candidate_file_exists_and_nonempty():
    labels = json.loads((CAND / "labels.json").read_text())
    for fname in labels:
        p = CAND / fname
        assert p.exists() and len(p.read_text().strip()) > 0
