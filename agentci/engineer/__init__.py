"""Engineer package: orchestrates one AgentCI check run (closed self-improving loop)."""
from agentci import config
from agentci.engineer.compare import fetch_baseline_via_mcp, compute_flips, is_regression
from agentci.engineer.mint import build_minted_case, persist_minted_case
from agentci.engineer.lift import evaluate_promotion, attach_independent_correctness, mean_correctness
from agentci.engineer.report import assemble_report
from agentci.evals.experiment import run_candidate
from agentci.data.dataset import load_tickets
from agentci.engineer.diagnose import diagnose
from agentci.engineer.fix_author import author_fix
from agentci.engineer.guard import run_guard, discrimination_test, load_persisted_guards
from agentci.engineer.review import review_rubric, passes_review
from agentci.memory import memory

_MCP_CALLS = {"n": 0}


def _mcp_call_count() -> int:
    return _MCP_CALLS["n"]


def _split(rows, split):
    return [r for r in rows if r["split"] == split]


def _ticket_index():
    return {t["id"]: t for t in load_tickets()}


def _gold_for(cluster) -> tuple[str, str]:
    """Pick a representative question + gold from the cluster's first case id."""
    by_id = _ticket_index()
    cid = (cluster.get("case_ids") or [None])[0]
    t = by_id.get(cid, {})
    return (t.get("question", f"Question about {cluster['label']}"),
            t.get("gold_resolution", cluster.get("summary", "")))


def _check_persisted_guards(cand_rows: list[dict]) -> dict:
    """Run every persisted guard against the candidate's answers. Return the first trip (D16)."""
    guards = load_persisted_guards(config.DATASET_NAME)
    answer_by_id = {r["id"]: r.get("answer", "") for r in cand_rows}
    for guard in guards:
        for cid in (guard.get("origin", {}).get("case_ids") or list(answer_by_id.keys())):
            if cid not in answer_by_id:
                continue
            if not run_guard(guard, answer_by_id[cid])["passed"]:
                return {"tripped": True, "guard": guard, "case_id": cid, "ran": len(guards)}
    return {"tripped": False, "guard": None, "ran": len(guards)}


def run_check(candidate_prompt: str, label: str) -> dict:
    """Run one AgentCI check: guard gate (D16) -> flip detection -> agentic diagnose (D11) +
    separate fix-author (D19) -> guard discrimination (D15) + review (D18) -> held-out lift on the
    cross-family ruler (D17). Proposes a fix + guard; persists nothing (human-approved, D12).

    Precondition: the baseline experiments ``baseline-tune`` and ``baseline-heldout`` must
    already exist in Phoenix and are read back THROUGH Phoenix MCP (GAP-4).
    """
    _MCP_CALLS["n"] = 0
    baseline = fetch_baseline_via_mcp("baseline-tune")
    _MCP_CALLS["n"] += 1
    baseline += fetch_baseline_via_mcp("baseline-heldout")
    _MCP_CALLS["n"] += 1

    cand_tune = run_candidate(candidate_prompt, config.DATASET_NAME, "tune", f"cand-{label}-tune")
    flips = compute_flips(_split(baseline, "tune"), cand_tune)
    prior_knowledge = memory.find_relevant(flips["pass_to_fail"])

    # GUARD GATE (D16): a candidate that trips a previously-minted guard is an instant red.
    guard_gate = _check_persisted_guards(cand_tune)
    if guard_gate.get("tripped"):
        meta = {"guards_active": guard_gate.get("ran", 0),
                "guard_tripped": (guard_gate.get("guard") or {}).get("slug"),
                "guard_admitted": None, "heldout_correctness": None, "heldout_lift": None}
        return assemble_report(label, True, flips, None, None, None, _mcp_call_count(),
                               guard_gate=guard_gate, meta_metrics=meta,
                               prior_knowledge=prior_knowledge)

    if not is_regression(_split(baseline, "tune"), cand_tune):
        meta = {"guards_active": guard_gate.get("ran", 0), "guard_tripped": None,
                "guard_admitted": None, "heldout_correctness": None, "heldout_lift": None}
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count(),
                               guard_gate=guard_gate, meta_metrics=meta,
                               prior_knowledge=prior_knowledge)

    # AGENTIC diagnosis (D11/D15/D19): root cause + taxonomy + headline + authored guard.
    diagnosis = diagnose(candidate_prompt, label, flips["pass_to_fail"], prior_lessons=prior_knowledge)
    _MCP_CALLS["n"] += int(diagnosis.get("mcp_calls", 0))
    cluster = diagnosis["root_cause"]
    guard = diagnosis["guard"]
    headline = diagnosis.get("headline_example", {})

    # Separate fix-author agent (D19).
    fix = author_fix(candidate_prompt, cluster)

    # Guard admission (D15): two-sided discrimination using the headline's wrong vs correct answers.
    disc = discrimination_test(guard, bad_answer=headline.get("candidate_answer", ""),
                               good_answer=headline.get("baseline_answer", ""))
    proposed_guard = {**guard, **disc}

    # Adversarial review for rubric guards (D18).
    guard_review = None
    if guard.get("kind") == "rubric":
        guard_review = review_rubric(guard)

    admitted = disc["admitted"] and (guard_review is None or passes_review(guard_review))

    # Validate the fix on held-out, scored by the independent-family ruler (D17).
    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    by_id = _ticket_index()
    fixed_heldout = attach_independent_correctness(
        fixed_heldout,
        {r["id"]: by_id.get(r["id"], {}).get("gold_resolution", "") for r in fixed_heldout})
    baseline_heldout = attach_independent_correctness(
        _split(baseline, "held_out"),
        {r["id"]: by_id.get(r["id"], {}).get("gold_resolution", "") for r in _split(baseline, "held_out")})
    promotion = evaluate_promotion(baseline_heldout, fixed_heldout)

    # Propose the minted case + guard only if promotable AND the guard earned admission (D12/D15).
    proposed_mint = None
    if promotion["promotable"] and admitted:
        q, gold = _gold_for(cluster)
        proposed_mint = build_minted_case(cluster, q, gold, guard=guard)

    meta = {"guards_active": guard_gate.get("ran", 0), "guard_tripped": None,
            "guard_admitted": proposed_guard.get("admitted") if proposed_guard else None,
            "heldout_correctness": mean_correctness(fixed_heldout),
            "heldout_lift": promotion["lift"] if promotion else None}

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count(),
                           investigation=diagnosis, proposed_mint=proposed_mint,
                           guard_gate=guard_gate, proposed_guard=proposed_guard,
                           guard_review=guard_review, meta_metrics=meta,
                           prior_knowledge=prior_knowledge)
