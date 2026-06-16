from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from src.workflow import (
    AgentWorkflowResult,
    AGENT_SCENARIOS,
    WorkflowPlan,
    WorkflowStep,
    propose_autonomous_workflow_plan,
    run_agent_workflow,
    validate_workflow_plan,
)
import src.workflow.agent as agent_module


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


def test_run_agent_workflow_full_scenario(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "run_full_risk_agent_workflow",
        lambda *args, **kwargs: SimpleNamespace(
            user_report="Combined Executive Summary\nMarket Risk\nCredit Risk",
            execution_trace=[
                {
                    "step_number": 1,
                    "tool_name": "calculate_risk_metrics",
                    "status": "success",
                }
            ],
            validation_result={"passed": True},
            raw_outputs={"market_risk": {}, "credit_risk": {}, "regulatory_risk": {}},
        ),
    )

    result = run_agent_workflow(scenario="full")

    assert isinstance(result, AgentWorkflowResult)
    assert result.scenario == "full"
    assert result.detected_modules == ["Market Risk", "Credit Risk", "Regulatory Risk"]
    assert result.plan_validation_result.passed is True
    assert result.approved_plan is not None
    assert "Combined Executive Summary" in result.user_report
    assert result.execution_trace[0]["tool_name"] == "calculate_risk_metrics"
    assert result.validation_result == {"passed": True}
    assert "market_risk" in result.raw_outputs


def test_run_agent_workflow_market_only_scenario(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "run_risk_workflow",
        lambda *args, **kwargs: SimpleNamespace(
            execution_trace=[
                SimpleNamespace(
                    step_number=1,
                    tool_name="calculate_risk_metrics",
                    status="success",
                    input_summary="Market inputs.",
                    output_summary="Market metrics.",
                    error=None,
                )
            ],
            validation_result=SimpleNamespace(passed=True),
        ),
    )

    result = run_agent_workflow(scenario="market")

    assert result.detected_modules == ["Market Risk"]
    assert "Market Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "calculate_risk_metrics"
    assert "market_risk" in result.raw_outputs


def test_run_agent_workflow_credit_only_scenario(monkeypatch):
    monkeypatch.setattr(
        agent_module,
        "run_risk_workflow",
        lambda *args, **kwargs: SimpleNamespace(
            execution_trace=[
                SimpleNamespace(
                    step_number=1,
                    tool_name="calculate_pfe_metrics",
                    status="success",
                    input_summary="Credit inputs.",
                    output_summary="PFE metrics.",
                    error=None,
                )
            ],
            validation_result=SimpleNamespace(passed=True),
        ),
    )

    result = run_agent_workflow(scenario="credit")

    assert result.detected_modules == ["Credit Risk"]
    assert "Credit Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "calculate_pfe_metrics"
    assert "credit_risk" in result.raw_outputs


def test_run_agent_workflow_regulatory_only_scenario():
    result = run_agent_workflow(scenario="regulatory")

    assert result.detected_modules == ["Regulatory Risk"]
    assert "Regulatory Risk" in result.final_report_summary
    assert result.execution_trace[0]["tool_name"] == "assess_regulatory_readiness"
    assert result.validation_result.passed is True
    assert "regulatory_risk" in result.raw_outputs


def test_run_agent_workflow_invalid_plan_does_not_execute(monkeypatch):
    def fail_if_executed(*args, **kwargs):
        raise AssertionError("Execution should not start for an invalid plan.")

    monkeypatch.setattr(agent_module, "run_full_risk_agent_workflow", fail_if_executed)
    monkeypatch.setattr(agent_module, "run_risk_workflow", fail_if_executed)
    invalid_plan = WorkflowPlan(
        objective="Invalid autonomous plan.",
        steps=[
            WorkflowStep(
                name="calculate_sa_ccr_capital",
                description="Unsupported capital calculation.",
                status="proposed",
                tool_name="calculate_sa_ccr_capital",
            )
        ],
    )

    result = run_agent_workflow(scenario="full", proposed_plan=invalid_plan)

    assert result.plan_validation_result.passed is False
    assert result.approved_plan is None
    assert result.execution_trace == []
    assert result.raw_outputs == {}
    assert result.final_report_summary == "Approved Plan: none; execution was not started."


def _load_demo_module():
    demo_path = Path("examples/run_autonomous_planning_demo.py")
    spec = importlib.util.spec_from_file_location("run_autonomous_planning_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_autonomous_demo_scenarios_detect_distinct_modules(monkeypatch, capsys):
    module = _load_demo_module()
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

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
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

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
    monkeypatch.setattr(module, "run_agent_workflow", _fake_run_agent_workflow)

    module.main(["--scenario", "full", "--show-plan"])

    output = capsys.readouterr().out
    assert "load_exposure_profile - Load counterparty exposure profile" in output
    assert output.index("load_exposure_profile") < output.index("calculate_pfe_metrics")


def _fake_run_agent_workflow(query=None, scenario="full", proposed_plan=None):
    scenario_config = AGENT_SCENARIOS[scenario]
    effective_query = query or scenario_config.query
    plan = proposed_plan or propose_autonomous_workflow_plan(
        effective_query,
        available_input_schemas=scenario_config.available_input_schemas,
        requested_modules=scenario_config.requested_modules,
    )
    validation_result = validate_workflow_plan(plan)
    return AgentWorkflowResult(
        query=effective_query,
        scenario=scenario,
        detected_modules=scenario_config.requested_modules,
        proposed_plan=plan,
        plan_validation_result=validation_result,
        approved_plan=plan if validation_result.passed else None,
        user_report="Fake user report.",
        final_report_summary=f"- Final report sections: {scenario}",
        execution_trace=[{"step_number": 1, "tool_name": "fake_tool"}],
        validation_result={"passed": validation_result.passed},
        raw_outputs={},
    )
