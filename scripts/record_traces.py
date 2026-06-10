"""One-shot: send real OpenInference traces to Phoenix (target agent, judges, investigator).

The demo cache replays everything, so `agentci check` fires no model calls and produces no spans.
This script uses a separate cache dir (.agentci_cache_traces) to force a small set of live calls
with tracing registered: 3 target-agent answers, the 4 judges on each, and one full investigator
diagnose (the reason-act loop with its Phoenix MCP tool calls — the spans that matter).

Run:  set -a; source .env; set +a; uv run python scripts/record_traces.py
"""
import os

os.environ["AGENTCI_CACHE_MODE"] = "record"
os.environ["AGENTCI_CACHE_DIR"] = ".agentci_cache_traces"

from agentci.tracing import init_tracing

provider = init_tracing()

from agentci import config
from agentci.data.dataset import load_tickets, _kb_text
from agentci.target.run import answer_ticket
from agentci.evals import judges


def main():
    kb = _kb_text()
    for t in [t for t in load_tickets() if t["split"] == "held_out"][:3]:
        ans = answer_ticket(config.BASELINE_SUPPORT_PROMPT, t["question"])
        print(f"{t['id']} answered: {ans['answer'][:70]!r}")
        exp, md = {"gold_resolution": t["gold_resolution"]}, {"kb": kb, "policy_id": t["policy_id"]}
        for dim in config.RUBRIC_DIMENSIONS:
            print(f"  {dim}: {getattr(judges, dim)(ans, exp, md)}")

    from agentci.engineer.diagnose import diagnose

    candidate = open("candidates/reg_refund.txt").read().strip()
    d = diagnose(candidate, "reg_refund", ["t06", "t08", "t12"])
    print("investigator root cause:", d["root_cause"].get("summary", "")[:100])
    print("investigator mcp_calls:", d.get("mcp_calls"))

    provider.force_flush()
    print("spans flushed to Phoenix project:", os.environ.get("PHOENIX_PROJECT_NAME", "agentci"))


if __name__ == "__main__":
    main()
