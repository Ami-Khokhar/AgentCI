"""Run the labeled candidate battery and score detection (GAP-1 proof, GAP-2 FP guard)."""
import json
from pathlib import Path

from agentci.engineer import run_check

_CAND_DIR = Path("candidates")


def build_confusion_matrix(reports: dict, labels: dict) -> dict:
    """Score regression detection. expected_regression iff label=='regressive'."""
    tp = fp = tn = fn = 0
    for fname, report in reports.items():
        expected = labels[fname] == "regressive"
        predicted = bool(report["regression_detected"])
        if expected and predicted:
            tp += 1
        elif expected and not predicted:
            fn += 1
        elif not expected and predicted:
            fp += 1
        else:
            tn += 1
    negatives = tn + fp
    fpr = round(fp / negatives, 4) if negatives else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "false_positive_rate": fpr}


def run_battery() -> dict:
    """Run all six labeled candidates through run_check; return reports + confusion matrix."""
    labels = json.loads((_CAND_DIR / "labels.json").read_text(encoding="utf-8"))
    reports = {}
    for fname, label in labels.items():
        prompt = (_CAND_DIR / fname).read_text(encoding="utf-8").strip()
        reports[fname] = run_check(prompt, label)
    confusion = build_confusion_matrix(reports, labels)
    return {"reports": reports, "confusion": confusion}
