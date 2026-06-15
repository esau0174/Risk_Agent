from __future__ import annotations

from src.report_validator import ValidationCheck, ValidationResult
from src.core.tool_registry import list_registered_tools
from src.workflow import ExecutionTraceEntry, WorkflowPlan, WorkflowStep
from examples.demo_utils import (
    print_execution_trace,
    print_input_summary,
    print_methodology_notes,
    print_registered_tools_by_module,
    print_validation_result,
    print_workflow_plan,
)


def test_shared_demo_helpers_render_common_sections(capsys):
    print_input_summary(
        "Analyze risk.",
        "portfolio.csv",
        "risk.json",
        ["shared", "market_risk"],
    )
    print_registered_tools_by_module(list_registered_tools())
    print_workflow_plan(
        WorkflowPlan(
            objective="Analyze risk.",
            steps=[
                WorkflowStep(
                    name="validate_report",
                    description="Validate report.",
                    status="completed",
                    tool_name="validate_report",
                    output_summary="Validation passed.",
                )
            ],
        )
    )
    print_execution_trace(
        [
            ExecutionTraceEntry(
                step_number=1,
                tool_name="validate_report",
                status="success",
                input_summary="Generated report.",
                output_summary="Validation passed.",
                error=None,
            )
        ]
    )
    print_methodology_notes([{"title": "Model Limitations"}])
    print_validation_result(
        ValidationResult(
            passed=True,
            checks=[ValidationCheck("guardrail", True, "Guardrail passed.")],
            errors=[],
            warnings=[],
        )
    )

    output = capsys.readouterr().out
    assert "Input Summary" in output
    assert "Data file: portfolio.csv" in output
    assert "Portfolio file:" not in output
    assert "Active modules: Shared, Market Risk" in output
    assert "Registered Risk Tools" in output
    assert "Shared:" in output
    assert "Market Risk:" in output
    assert "Credit Risk:" in output
    assert "Workflow Plan" in output
    assert "Execution Trace" in output
    assert "Retrieved Methodology Notes" in output
    assert "Report Validation" in output
