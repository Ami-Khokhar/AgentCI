from agentci.engineer.battery import build_confusion_matrix

def test_confusion_matrix_counts():
    reports = {
        "reg_refund.txt": {"regression_detected": True},
        "reg_routing.txt": {"regression_detected": True},
        "benign_reword.txt": {"regression_detected": False},
        "benign_format.txt": {"regression_detected": False},
        "improve_cite.txt": {"regression_detected": False},
        "improve_clarify.txt": {"regression_detected": False},
    }
    labels = {
        "reg_refund.txt": "regressive", "reg_routing.txt": "regressive",
        "benign_reword.txt": "benign", "benign_format.txt": "benign",
        "improve_cite.txt": "improving", "improve_clarify.txt": "improving",
    }
    cm = build_confusion_matrix(reports, labels)
    assert cm == {"tp": 2, "fp": 0, "tn": 4, "fn": 0, "false_positive_rate": 0.0}

def test_false_positive_is_counted():
    reports = {"benign_reword.txt": {"regression_detected": True}}
    labels = {"benign_reword.txt": "benign"}
    cm = build_confusion_matrix(reports, labels)
    assert cm["fp"] == 1 and cm["false_positive_rate"] == 1.0
