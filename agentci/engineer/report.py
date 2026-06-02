"""Assemble the terminal run report consumed by the CLI and dashboard."""


def assemble_report(candidate_label, regression, flips, cluster, fix, promotion, mcp_calls,
                    investigation=None, proposed_mint=None, guard_gate=None,
                    proposed_guard=None, guard_review=None, meta_metrics=None):
    """Build the run report. Encodes all terminal outcomes incl. guard-block (D16) and no-fix->RED."""
    if guard_gate and guard_gate.get("tripped"):
        verdict, gate = "guard_blocked", "red"          # D16: hard block on a learned guard
    elif not regression:
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
        "investigation": investigation,
        "proposed_mint": proposed_mint,
        "guard_gate": guard_gate,          # NEW (D16): persisted guards run + any trip
        "proposed_guard": proposed_guard,  # NEW (D15): authored guard + discrimination evidence
        "guard_review": guard_review,      # NEW (D18): adversarial reviewer verdict
        "meta_metrics": meta_metrics,      # NEW (spec §5.10): surfaced by Plan 07
        "mcp_calls": mcp_calls,
        "verdict": verdict,
        "gate": gate,
    }
