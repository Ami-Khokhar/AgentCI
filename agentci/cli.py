"""AgentCI command line: run a regression check on a candidate prompt."""
import json
from pathlib import Path

import click

from agentci.engineer import run_check

_GATE_MARK = {"green": "GREEN ✅", "red": "RED ⛔"}


@click.group()
def cli():
    """AgentCI — regression CI for AI agents."""


@cli.command()
@click.option("--candidate", "candidate", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Path to a candidate system-prompt .txt file.")
@click.option("--label", default=None, help="Run label (defaults to the candidate file stem).")
@click.option("--runs-dir", default="runs", help="Directory to write the run report JSON into.")
def check(candidate, label, runs_dir):
    """Run a regression check on a candidate prompt and write its report."""
    import os
    if os.environ.get("AGENTCI_CACHE_MODE", "replay") in ("record", "live"):
        # OpenInference tracing only when model calls actually fire — replay mode is offline
        # by contract (tests, demo) and must not touch the Phoenix collector.
        from agentci.tracing import init_tracing
        init_tracing()

    prompt = Path(candidate).read_text(encoding="utf-8").strip()
    label = label or Path(candidate).stem
    report = run_check(prompt, label)

    out_dir = Path(runs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{label}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    click.echo(f"candidate : {label}")
    click.echo(f"gate      : {_GATE_MARK.get(report['gate'], report['gate'])}")
    click.echo(f"verdict   : {report['verdict']}")
    if report["regression_detected"]:
        click.echo(f"flipped   : {report['flips']['pass_to_fail']}")
        if report.get("promotion"):
            click.echo(f"held-out  : {report['promotion']['reason']}")
    click.echo(f"mcp calls : {report['mcp_calls']}")
    click.echo(f"report    : {report_path}")
    click.echo(f"dashboard : http://127.0.0.1:8000/?run={label}")


@cli.command()
@click.option("--run", "run_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Path to a run report JSON to approve.")
def approve(run_path):
    """Approve a green_promotable_fix run: promote the fix, mint the case, write Quality Memory (D12)."""
    from datetime import datetime, timezone

    from agentci.engineer.mint import approve_and_mint
    from agentci.memory import memory

    path = Path(run_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("gate") != "green" or not report.get("proposed_mint"):
        raise click.ClickException("nothing to approve (gate not green / no proposed mint)")
    if report.get("minted"):
        raise click.ClickException("already approved — nothing to do")

    minted = approve_and_mint(report)
    entry = memory.record_approval(report, datetime.now(timezone.utc).isoformat())
    report["minted"] = minted
    report["memory_entry"] = entry
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    click.echo(f"approved : {report.get('candidate_label')}")
    click.echo(f"minted   : {minted['id'] if minted else '—'}")
    click.echo(f"memory   : {entry['failure_type']} — {entry['lesson']}")
