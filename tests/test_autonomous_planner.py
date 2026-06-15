from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.workflow import (
    WorkflowPlan,
    WorkflowStep,
    propose_autonomous_workflow_plan,
    validate_workflow_plan,
)


def test_autonomous_planner_proposes_all_requested_risk_modules():
    plan = propose_autonomous_workflow_plan(
        "Run Market Risk, Credit Risk, and Regulatory Risk with stress testing.",
        available_input_schemas=["market_portfolio", "exposure_profile"],
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
    )

    tool_names = [step.tool_name for step in plan.steps]

    assert "calculate_risk_metrics" in tool_names
    assert "run_stress_test" in tool_names
    assert "calculate_pfe_metrics" in tool_names
    assert "assess_regulatory_readiness" in tool_names
    assert set(tool_names) <= {
        "load_portfolio_file",
        "validate_portfolio",
        "load_risk_config",
        "calculate_risk_metrics",
        "run_stress_test",
        "calculate_pfe_metrics",
        "assess_regulatory_readiness",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    }


def test_plan_validator_accepts_valid_autonomous_plan():
    plan = propose_autonomous_workflow_plan(
        "Run Market Risk, Credit Risk, and Regulatory Risk with stress testing.",
        available_input_schemas=["market_portfolio", "exposure_profile"],
        requested_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is True
    assert result.errors == []


def test_plan_validator_rejects_unsupported_regulatory_capital_tool():
    plan = WorkflowPlan(
        objective="Invalid regulatory capital request.",
        steps=[
            WorkflowStep(
                name="calculate_sa_ccr_capital",
                description="Unsupported SA-CCR capital calculation.",
                status="proposed",
                tool_name="calculate_sa_ccr_capital",
            )
        ],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is False
    assert any("Unsupported regulatory capital" in error for error in result.errors)


def test_plan_validator_rejects_misordered_tools():
    plan = WorkflowPlan(
        objective="Invalid market order.",
        steps=[
            WorkflowStep(
                name="calculate_risk_metrics",
                description="Calculate risk before validation.",
                status="proposed",
                tool_name="calculate_risk_metrics",
            ),
            WorkflowStep(
                name="validate_portfolio",
                description="Validate portfolio too late.",
                status="proposed",
                tool_name="validate_portfolio",
            ),
            WorkflowStep(
                name="generate_commentary",
                description="Generate commentary.",
                status="proposed",
                tool_name="generate_commentary",
            ),
            WorkflowStep(
                name="validate_report",
                description="Validate report.",
                status="proposed",
                tool_name="validate_report",
            ),
        ],
    )

    result = validate_workflow_plan(plan)

    assert result.passed is False
    assert "validate_portfolio must occur before calculate_risk_metrics." in (
        result.errors
    )


def _load_demo_module():
    demo_path = Path("examples/run_autonomous_planning_demo.py")
    spec = importlib.util.spec_from_file_location("run_autonomous_planning_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_autonomous_demo_scenarios_detect_distinct_modules(monkeypatch, capsys):
    module = _load_demo_module()
    monkeypatch.setattr(
        module,
        "_print_execution_summary",
        lambda scenario: print(f"- Final report sections: {scenario}"),
    )

    expected_modules = {
        "market": "Detected modules: Market Risk",
        "credit": "Detected modules: Credit Risk",
        "regulatory": "Detected modules: Regulatory Risk",
        "full": "Detected modules: Market Risk, Credit Risk, Regulatory Risk",
    }
    for scenario, expected_line in expected_modules.items():
        module.main(["--scenario", scenario])
        output = capsys.readouterr().out
        assert expected_line in output
        assert "Approved Tool Sequence" not in output
        assert "Final Report Summary" in output


def test_autonomous_demo_custom_query_and_show_plan(monkeypatch, capsys):
    module = _load_demo_module()
    monkeypatch.setattr(
        module,
        "_print_execution_summary",
        lambda scenario: print(f"- Final report sections: {scenario}"),
    )

    module.main(
        [
            "--scenario",
            "market",
            "--query",
            "Custom market risk request",
            "--show-plan",
        ]
    )

    output = capsys.readouterr().out
    assert "- Query: Custom market risk request" in output
    assert "Approved Tool Sequence" in output
    assert "calculate_risk_metrics" in output


def test_autonomous_demo_full_plan_displays_credit_exposure_loading(
    monkeypatch,
    capsys,
):
    module = _load_demo_module()
    monkeypatch.setattr(
        module,
        "_print_execution_summary",
        lambda scenario: print(f"- Final report sections: {scenario}"),
    )

    module.main(["--scenario", "full", "--show-plan"])

    output = capsys.readouterr().out
    assert "load_exposure_profile - Load counterparty exposure profile" in output
    assert output.index("load_exposure_profile") < output.index("calculate_pfe_metrics")
