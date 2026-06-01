import json
from pathlib import Path

from click.testing import CliRunner

from agentci import cli as cli_mod

def test_check_writes_report_and_prints_gate(monkeypatch):
    canned = {"candidate_label": "reg-refund", "regression_detected": True,
              "flips": {"pass_to_fail": ["t00"], "fail_to_pass": []},
              "promotion": {"reason": "held-out lift +0.200 >= 0.05, no held-out regressions",
                            "promotable": True},
              "mcp_calls": 5, "verdict": "green_promotable_fix", "gate": "green"}
    monkeypatch.setattr(cli_mod, "run_check", lambda prompt, label: canned)
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("cand.txt").write_text("SOME CANDIDATE PROMPT")
        result = runner.invoke(cli_mod.cli, ["check", "--candidate", "cand.txt", "--label", "reg-refund"])
        assert result.exit_code == 0, result.output
        assert "GREEN" in result.output
        assert "reg-refund" in result.output
        data = json.loads(Path("runs/reg-refund.json").read_text())
        assert data["verdict"] == "green_promotable_fix"

def test_check_defaults_label_to_filename_stem(monkeypatch):
    canned = {"candidate_label": "cand", "regression_detected": False,
              "flips": {"pass_to_fail": [], "fail_to_pass": []},
              "promotion": None, "mcp_calls": 2,
              "verdict": "green_no_regression", "gate": "green"}
    monkeypatch.setattr(cli_mod, "run_check", lambda prompt, label: canned)
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("cand.txt").write_text("PROMPT")
        result = runner.invoke(cli_mod.cli, ["check", "--candidate", "cand.txt"])
        assert result.exit_code == 0, result.output
        assert Path("runs/cand.json").exists()
