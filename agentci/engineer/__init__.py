"""Engineer package: orchestrates one AgentCI check run."""
from agentci import config
from agentci.engineer.compare import fetch_baseline_via_mcp, compute_flips, is_regression
from agentci.engineer.cluster import cluster_failures
from agentci.engineer.fix import draft_fix
from agentci.engineer.mint import build_minted_case, persist_minted_case
from agentci.engineer.lift import evaluate_promotion
from agentci.engineer.report import assemble_report
from agentci.evals.experiment import run_candidate
from agentci.data.dataset import load_tickets

_MCP_CALLS = {"n": 0}


def _mcp_call_count() -> int:
    return _MCP_CALLS["n"]


def _split(rows, split):
    return [r for r in rows if r["split"] == split]


def _gold_for(cluster) -> tuple[str, str]:
    """Pick a representative question + gold from the cluster's first case id."""
    by_id = {t["id"]: t for t in load_tickets()}
    cid = (cluster.get("case_ids") or [None])[0]
    t = by_id.get(cid, {})
    return (t.get("question", f"Question about {cluster['label']}"),
            t.get("gold_resolution", cluster.get("summary", "")))


def run_check(candidate_prompt: str, label: str) -> dict:
    """Run one AgentCI check: detect -> (cluster -> fix -> held-out lift -> mint) -> report."""
    baseline = fetch_baseline_via_mcp("baseline-tune") + fetch_baseline_via_mcp("baseline-heldout")
    _MCP_CALLS["n"] = _mcp_call_count() or 0

    cand_tune = run_candidate(candidate_prompt, config.DATASET_NAME, "tune", f"cand-{label}-tune")
    flips = compute_flips(_split(baseline, "tune"), cand_tune)

    if not is_regression(_split(baseline, "tune"), cand_tune):
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count())

    failing = [{"id": cid} for cid in flips["pass_to_fail"]]
    by_id = {t["id"]: t for t in load_tickets()}
    cand_by_id = {r["id"]: r for r in cand_tune}
    cases = [{
        "id": cid,
        "question": by_id.get(cid, {}).get("question", ""),
        "gold": by_id.get(cid, {}).get("gold_resolution", ""),
        "answer": cand_by_id.get(cid, {}).get("answer", ""),  # present per Plan 02 row contract
    } for cid in flips["pass_to_fail"]]
    cluster = cluster_failures(cases)

    fix = draft_fix(candidate_prompt, cluster)
    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    promotion = evaluate_promotion(_split(baseline, "held_out"), fixed_heldout)

    if promotion["promotable"]:
        q, gold = _gold_for(cluster)
        persist_minted_case(build_minted_case(cluster, q, gold))

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count())
