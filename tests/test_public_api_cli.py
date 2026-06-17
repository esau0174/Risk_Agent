from __future__ import annotations

import importlib.util
from pathlib import Path

from riskflow_agent import run_agent_workflow, run_risk_workflow
from riskflow_agent.cli import main as cli_main


def test_public_api_exports_workflow_entry_points():
    assert callable(run_agent_workflow)
    assert callable(run_risk_workflow)


def test_cli_regulatory_smoke_path(capsys):
    cli_main(
        [
            "--planner",
            "rule",
            "--scenario",
            "regulatory",
            "--show-plan",
        ]
    )

    output = capsys.readouterr().out
    assert "RiskFlow Agent Demo" in output
    assert "Approved Tool Sequence" in output
    assert "Regulatory Risk" in output
    assert "Validation / Guardrail Summary" in output


def test_console_script_entry_point_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '[project.scripts]' in pyproject
    assert 'riskflow-agent = "riskflow_agent.cli:main"' in pyproject


def test_example_wrapper_still_exposes_primary_demo_main(monkeypatch, capsys):
    demo_path = Path("examples/run_riskflow_agent_demo.py")
    spec = importlib.util.spec_from_file_location("run_riskflow_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(
        module,
        "run_agent_workflow",
        lambda **kwargs: run_agent_workflow(
            scenario="regulatory",
            planner_mode="rule",
        ),
    )

    module.main(["--scenario", "regulatory", "--planner", "rule"])

    output = capsys.readouterr().out
    assert "RiskFlow Agent Demo" in output
    assert "Regulatory Risk" in output
