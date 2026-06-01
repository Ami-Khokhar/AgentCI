"""Engineer package: orchestrates one AgentCI check run."""
from agentci import config
from agentci.engineer.compare import fetch_baseline_via_mcp, compute_flips, is_regression
from agentci.engineer.mint import build_minted_case, persist_minted_case
from agentci.engineer.lift import evaluate_promotion
from agentci.engineer.report import assemble_report
from agentci.evals.experiment import run_candidate
from agentci.data.dataset import load_tickets
from agentci.engineer.investigate import investigate

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
    """Run one AgentCI check (D11/D12).

    Deterministic CI detects the regression; the AGENTIC investigator root-causes it and
    proposes a fix; the fix is validated on held-out; the report carries the proposed mint
    but does NOT persist it (minting happens on human approval, D12).

    Precondition: the baseline experiments ``baseline-tune`` and ``baseline-heldout`` must
    already exist in Phoenix (produced by running ``BASELINE_SUPPORT_PROMPT`` over each split)
    and are read back at runtime THROUGH Phoenix MCP (GAP-4) — never from a local copy.
    """
    # Count MCP-mediated reads so the report can evidence load-bearing MCP (GAP-4).
    _MCP_CALLS["n"] = 0
    baseline = fetch_baseline_via_mcp("baseline-tune")
    _MCP_CALLS["n"] += 1
    baseline += fetch_baseline_via_mcp("baseline-heldout")
    _MCP_CALLS["n"] += 1

    cand_tune = run_candidate(candidate_prompt, config.DATASET_NAME, "tune", f"cand-{label}-tune")
    flips = compute_flips(_split(baseline, "tune"), cand_tune)

    if not is_regression(_split(baseline, "tune"), cand_tune):
        return assemble_report(label, False, flips, None, None, None, _mcp_call_count())

    # AGENTIC investigation (D11): hypothesis -> agent-chosen Phoenix MCP queries -> root cause + fix.
    investigation = investigate(candidate_prompt, label, flips["pass_to_fail"])
    _MCP_CALLS["n"] += int(investigation.get("mcp_calls", 0))
    cluster = investigation["root_cause"]
    fix = investigation["proposed_fix"]

    fixed_heldout = run_candidate(fix["revised_prompt"], config.DATASET_NAME, "held_out", f"fixed-{label}-heldout")
    promotion = evaluate_promotion(_split(baseline, "held_out"), fixed_heldout)

    # D12: build the minted case as a PROPOSAL; it is persisted only on human approval.
    proposed_mint = None
    if promotion["promotable"]:
        q, gold = _gold_for(cluster)
        proposed_mint = build_minted_case(cluster, q, gold)

    return assemble_report(label, True, flips, cluster, fix, promotion, _mcp_call_count(),
                           investigation=investigation, proposed_mint=proposed_mint)
