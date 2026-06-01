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
