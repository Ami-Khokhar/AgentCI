"""One-shot calibration: does baseline-vs-baseline (same prompt, fresh sample) pass the D8 flip leg?

Phase 1 replays the recorded baseline held-out rows from the main cache. Phase 2 records a FRESH
sample of the same prompt/tickets into .agentci_cache_calib (record mode = fill-if-missing, so this
script is resumable). Then it applies the exact promotion-gate math to the two samples.

Run:  set -a; source .env; set +a; uv run python calibrate_gate.py
"""
import json
import os

from agentci import config
from agentci.data.dataset import load_tickets, _kb_text


def heldout_rows() -> list[dict]:
    from agentci import cache
    from agentci.target.run import answer_ticket
    from agentci.evals import judges
    from agentci.evals.experiment import case_passed
    from agentci.engineer.independent_judge import judge_correctness

    kb = _kb_text()
    rows = []
    for t in [t for t in load_tickets() if t["split"] == "held_out"]:
        ans = answer_ticket(config.BASELINE_SUPPORT_PROMPT, t["question"])["answer"]
        out, exp = {"answer": ans}, {"gold_resolution": t["gold_resolution"]}
        md = {"kb": kb, "policy_id": t["policy_id"]}
        scores = {dim: getattr(judges, dim)(out, exp, md) for dim in config.RUBRIC_DIMENSIONS}
        scores["correctness"] = judge_correctness(ans, t["gold_resolution"])
        rows.append({"id": t["id"], "split": "held_out", "answer": ans,
                     "scores": scores, "passed": case_passed(scores)})
    return rows


def main():
    from agentci.engineer.lift import evaluate_promotion

    os.environ["AGENTCI_CACHE_MODE"] = "replay"
    os.environ["AGENTCI_CACHE_DIR"] = ".agentci_cache"
    sample_a = heldout_rows()

    os.environ["AGENTCI_CACHE_MODE"] = "record"
    os.environ["AGENTCI_CACHE_DIR"] = ".agentci_cache_calib"
    sample_b = heldout_rows()

    gate = evaluate_promotion(sample_a, sample_b)
    print(json.dumps(gate, indent=2))
    for a, b in zip(sample_a, sample_b):
        flip = "P->F" if a["passed"] and not b["passed"] else ("F->P" if b["passed"] and not a["passed"] else "")
        if flip:
            dims = {d: (a["scores"][d], b["scores"][d]) for d in b["scores"]
                    if b["scores"][d] < config.PASS_THRESHOLD}
            print(a["id"], flip, dims)


if __name__ == "__main__":
    main()
