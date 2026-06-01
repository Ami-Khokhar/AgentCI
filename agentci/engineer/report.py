"""Assemble the terminal run report consumed by the CLI and dashboard."""


def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls):
    """Build the run report. Encodes all terminal outcomes incl. no-fix->RED (GAP-6)."""
    if not regression:
        verdict, gate = "green_no_regression", "green"
    elif promotion and promotion.get("promotable"):
        verdict, gate = "green_promotable_fix", "green"
    else:
        verdict, gate = "red_no_fix", "red"

    return {
        "candidate_label": candidate_label,
        "regression_detected": regression,
        "flips": flips,
        "cluster": cluster,
        "proposed_fix": fix,
        "promotion": promotion,
        "mcp_calls": mcp_calls,         # evidences load-bearing MCP (GAP-4)
        "verdict": verdict,
        "gate": gate,
    }
