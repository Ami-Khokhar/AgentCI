import json

from click.testing import CliRunner

from agentci.cli import cli


def test_approve_command_mints_and_records(tmp_path, monkeypatch):
    from agentci.engineer import mint
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    monkeypatch.setattr(mint, "approve_and_mint", lambda rep, ds=None: rep["proposed_mint"])

    report = {"candidate_label": "reg-concise", "gate": "green",
              "flips": {"pass_to_fail": ["t05"]},
              "investigation": {"root_cause": {"category": "factual_omission",
                                               "policy_id": "refund-policy", "summary": "s"}},
              "proposed_fix": {"rationale": "always cite refund policy"},
              "proposed_mint": {"id": "minted-refund-policy-0", "guard": '{"slug": "refund-window"}'}}
    run_path = tmp_path / "reg-concise.json"
    run_path.write_text(json.dumps(report))

    result = CliRunner().invoke(cli, ["approve", "--run", str(run_path)])
    assert result.exit_code == 0, result.output
    assert "minted-refund-policy-0" in result.output

    persisted = json.loads(run_path.read_text())
    assert persisted["memory_entry"]["failure_type"] == "factual_omission"

    from agentci.memory import memory
    assert len(memory.load_memory()) == 1


def test_approve_command_rejects_non_green(tmp_path):
    report = {"candidate_label": "reg", "gate": "red", "proposed_mint": None}
    run_path = tmp_path / "reg.json"
    run_path.write_text(json.dumps(report))
    result = CliRunner().invoke(cli, ["approve", "--run", str(run_path)])
    assert result.exit_code != 0
    assert "nothing to approve" in result.output


def test_approve_command_rejects_already_approved(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("AGENTCI_MEMORY_PATH", str(tmp_path / "qm.json"))
    report = {"candidate_label": "reg", "gate": "green",
              "proposed_mint": {"id": "m", "guard": "{}"}, "minted": {"id": "m"}}
    run_path = tmp_path / "reg.json"
    run_path.write_text(json.dumps(report))
    result = CliRunner().invoke(cli, ["approve", "--run", str(run_path)])
    assert result.exit_code != 0
    assert "already approved" in result.output
