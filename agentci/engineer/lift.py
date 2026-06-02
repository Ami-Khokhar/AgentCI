"""Held-out lift computation and the promotion gate (D8)."""
from agentci import config
from agentci.engineer.compare import compute_flips
from agentci.engineer.independent_judge import judge_correctness


def mean_correctness(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return round(sum(r["scores"]["correctness"] for r in rows) / len(rows), 4)


def evaluate_promotion(baseline_heldout: list[dict], fixed_heldout: list[dict]) -> dict:
    """Apply D8: promotable iff held-out correctness lift >= MIN_HELDOUT_LIFT AND zero
    held-out pass->fail flips. Returns the full decision record."""
    lift = round(mean_correctness(fixed_heldout) - mean_correctness(baseline_heldout), 4)
    regressions = len(compute_flips(baseline_heldout, fixed_heldout)["pass_to_fail"])
    promotable = lift >= config.MIN_HELDOUT_LIFT and regressions <= config.MAX_HELDOUT_REGRESSIONS
    if promotable:
        reason = f"held-out lift {lift:+.3f} >= {config.MIN_HELDOUT_LIFT}, no held-out regressions"
    elif regressions > config.MAX_HELDOUT_REGRESSIONS:
        reason = f"{regressions} held-out pass->fail flip(s) — gate stays RED"
    else:
        reason = f"held-out lift {lift:+.3f} < {config.MIN_HELDOUT_LIFT} — insufficient, gate stays RED"
    return {
        "lift": lift,
        "n": len(fixed_heldout),
        "heldout_regressions": regressions,
        "promotable": promotable,
        "reason": reason,
    }


def attach_independent_correctness(rows: list[dict], gold_by_id: dict[str, str]) -> list[dict]:
    """Re-score each row's correctness with the independent-family ruler (D17), so the held-out
    lift gate measures improvement on a brain the optimizer does not control. Returns new rows."""
    out = []
    for r in rows:
        row = dict(r)
        row["scores"] = dict(r["scores"])
        gold = gold_by_id.get(r["id"], "")
        row["scores"]["correctness"] = judge_correctness(r.get("answer", ""), gold)
        out.append(row)
    return out
