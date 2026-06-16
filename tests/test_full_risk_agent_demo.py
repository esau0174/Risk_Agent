from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.workflow import AgentWorkflowResult, WorkflowPlan


def _load_demo_module():
    demo_path = Path("examples/run_riskflow_agent_demo.py")
    spec = importlib.util.spec_from_file_location("run_riskflow_agent_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agent_result() -> AgentWorkflowResult:
    plan = WorkflowPlan(objective="Test plan.", steps=[])
    return AgentWorkflowResult(
        query="Run the full RiskFlow Agent workflow.",
        scenario="full",
        detected_modules=["Market Risk", "Credit Risk", "Regulatory Risk"],
        proposed_plan=plan,
        plan_validation_result=type(
            "PlanValidation",
            (),
            {"passed": True, "errors": [], "warnings": []},
        )(),
        approved_plan=plan,
        user_report="Combined Executive Summary\nMarket Risk and Credit Risk",
        execution_trace=[
            {
                "step_number": 1,
                "tool_name": "load_portfolio_file",
                "status": "success",
                "input_summary": "Market data file.",
                "output_summary": "Loaded holdings.",
                "error": None,
                "workflow": "market_risk",
            }
        ],
        validation_result={"passed": True},
        final_report_summary="- Validation: PASSED",
        raw_outputs={"market_risk": {}, "credit_risk": {}},
    )


def _agent_result_for(
    scenario: str,
    detected_modules: list[str],
    user_report: str,
) -> AgentWorkflowResult:
    plan = WorkflowPlan(objective="Test plan.", steps=[])
    return AgentWorkflowResult(
        query="Test query.",
        scenario=scenario,
        detected_modules=detected_modules,
        proposed_plan=plan,
        plan_validation_result=type(
            "PlanValidation",
            (),
            {"passed": True, "errors": [], "warnings": []},
        )(),
        approved_plan=plan,
        user_report=user_report,
        execution_trace=[],
        validation_result={"passed": True},
        final_report_summary="- Validation: PASSED",
        raw_outputs={},
    )


def test_primary_demo_prints_planning_context_and_user_report(monkeypatch, capsys):
    module = _load_demo_module()
    result = _agent_result()
    monkeypatch.setattr(module, "run_agent_workflow", lambda **kwargs: result)

    module.main([])

    output = capsys.readouterr().out
    assert "RiskFlow Agent Demo" in output
    assert "User Request" in output
    assert "Input Context" in output
    assert "Autonomous Planning Summary" in output
    assert "Risk Report" in output
    assert result.user_report in output
    assert "Validation / Guardrail Summary" in output


def test_primary_demo_optionally_saves_execution_trace(monkeypatch, tmp_path):
    module = _load_demo_module()
    result = _agent_result()
    trace_path = tmp_path / "full_demo_trace.json"
    monkeypatch.setattr(module, "run_agent_workflow", lambda **kwargs: result)

    module.main(["--trace-file", str(trace_path)])

    trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace_payload == {
        "orchestration_trace": result.orchestration_trace,
        "execution_trace": result.execution_trace,
    }


def test_primary_demo_prints_selected_module_reports(monkeypatch, capsys):
    module = _load_demo_module()
    reports = {
        "market": _agent_result_for(
            "market",
            ["Market Risk"],
            "Market Risk\n- Annualized volatility: 26.71%",
        ),
        "credit": _agent_result_for(
            "credit",
            ["Credit Risk"],
            "Credit Risk\n- Peak 95% PFE: USD 2,100,000.00",
        ),
        "regulatory": _agent_result_for(
            "regulatory",
            ["Regulatory Risk"],
            "Regulatory Risk\n- SA-CCR readiness: WARNING",
        ),
    }
    monkeypatch.setattr(
        module,
        "run_agent_workflow",
        lambda **kwargs: reports[kwargs["scenario"]],
    )

    expected_lines = {
        "market": "Annualized volatility: 26.71%",
        "credit": "Peak 95% PFE: USD 2,100,000.00",
        "regulatory": "SA-CCR readiness: WARNING",
    }
    for scenario, expected_line in expected_lines.items():
        module.main(["--scenario", scenario])
        output = capsys.readouterr().out
        assert expected_line in output
        assert "Risk Report" in output


def test_primary_demo_custom_query_can_detect_regulatory_only(monkeypatch, capsys):
    module = _load_demo_module()

    def fake_run_agent_workflow(**kwargs):
        assert kwargs["query"] == "Check SA-CCR and SIMM readiness only."
        return _agent_result_for(
            "full",
            ["Regulatory Risk"],
            "Regulatory Risk\n- SA-CCR readiness: WARNING",
        )

    monkeypatch.setattr(module, "run_agent_workflow", fake_run_agent_workflow)

    module.main(["--query", "Check SA-CCR and SIMM readiness only."])

    output = capsys.readouterr().out
    assert "Requested modules: Regulatory Risk" in output
    assert "SA-CCR readiness: WARNING" in output
