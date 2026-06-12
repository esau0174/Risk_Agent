from __future__ import annotations

from dataclasses import replace

import pytest

from src.report_validator import ValidationResult
from src.tool_executor import ToolExecutor
from src.tool_registry import list_registered_tools
from src.workflow import WorkflowResult, build_risk_workflow_plan, run_risk_workflow


def _fake_generate_portfolio_risk_report(
    tickers,
    weights,
    start_date,
    end_date=None,
    confidence_level=0.95,
):
    return {
        "metadata": {
            "tickers": list(tickers),
            "weights": list(weights),
            "start_date": start_date,
            "end_date": end_date,
            "confidence_level": confidence_level,
        },
        "risk_metrics": {
            "annualized_volatility": 0.20,
            "historical_var": 0.02,
            "expected_shortfall": 0.03,
            "max_drawdown": 0.15,
        },
        "correlation_matrix": {
            "SPY": {"SPY": 1.0, "QQQ": 0.8},
            "QQQ": {"SPY": 0.8, "QQQ": 1.0},
        },
        "latest_cumulative_return": 0.25,
        "number_of_observations": 10,
        "analysis_timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_build_risk_workflow_plan_returns_expected_steps():
    plan = build_risk_workflow_plan("40% SPY, 60% QQQ")

    assert plan.objective == "Analyze portfolio risk from a natural-language query."
    assert [step.name for step in plan.steps] == [
        "parse_portfolio",
        "validate_portfolio",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert [step.tool_name for step in plan.steps] == [
        "parse_portfolio",
        "validate_portfolio",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert all(step.status == "pending" for step in plan.steps)


def test_run_risk_workflow_without_llm_returns_completed_result():
    tools = [
        replace(tool, handler=_fake_generate_portfolio_risk_report)
        if tool.name == "calculate_risk_metrics"
        else tool
        for tool in list_registered_tools()
    ]
    executor = ToolExecutor(tools)

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=executor,
    )

    assert isinstance(result, WorkflowResult)
    assert all(step.status == "completed" for step in result.plan.steps)
    assert all(step.output_summary for step in result.plan.steps)
    assert result.parsed_portfolio == {
        "tickers": ["SPY", "QQQ"],
        "weights": [0.4, 0.6],
    }
    assert result.risk_report["risk_metrics"]["historical_var"] == 0.02
    assert result.methodology_notes
    assert "not investment advice" in result.llm_commentary
    assert result.validation_result.passed is True
    assert any(step.name == "validate_report" for step in result.plan.steps)
    assert [entry.tool_name for entry in result.execution_trace] == [
        "parse_portfolio",
        "validate_portfolio",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
    ]
    assert [entry.step_number for entry in result.execution_trace] == [1, 2, 3, 4, 5, 6]
    assert all(entry.status == "success" for entry in result.execution_trace)
    assert all(entry.input_summary for entry in result.execution_trace)
    assert all(entry.output_summary for entry in result.execution_trace)
    assert all(entry.error is None for entry in result.execution_trace)
    assert not any(
        entry.tool_name == "regenerate_commentary_with_validation_errors"
        for entry in result.execution_trace
    )
    assert result.warnings == [
        "LLM commentary disabled; returned deterministic fallback commentary."
    ]


def test_failed_tool_execution_is_recorded_before_workflow_raises():
    def failing_parser(query):
        raise ValueError("unable to parse portfolio")

    tools = [
        replace(tool, handler=failing_parser)
        if tool.name == "parse_portfolio"
        else tool
        for tool in list_registered_tools()
    ]
    executor = ToolExecutor(tools)

    with pytest.raises(RuntimeError, match="parse_portfolio") as exc_info:
        run_risk_workflow(
            "invalid portfolio query",
            use_llm=False,
            tool_executor=executor,
        )

    trace = exc_info.value.execution_trace
    assert len(trace) == 1
    assert trace[0].step_number == 1
    assert trace[0].tool_name == "parse_portfolio"
    assert trace[0].status == "failed"
    assert trace[0].input_summary == "Natural-language portfolio query."
    assert trace[0].output_summary == "Tool execution produced no output."
    assert trace[0].error == "ValueError: unable to parse portfolio"


def test_validation_failure_regenerates_commentary_once_and_revalidates():
    validation_results = iter(
        [
            ValidationResult(False, [], ["unsafe commentary"], []),
            ValidationResult(True, [], [], []),
        ]
    )
    regeneration_calls = []

    def validate_once_then_pass(*args):
        return next(validation_results)

    def regenerate(*args, **kwargs):
        regeneration_calls.append((args, kwargs))
        return "Regenerated commentary with assumptions and limitations; not investment advice."

    replacements = {
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
        "generate_commentary": lambda *args, **kwargs: "Unsafe original commentary.",
        "validate_report": validate_once_then_pass,
        "regenerate_commentary_with_validation_errors": regenerate,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert len(regeneration_calls) == 1
    regeneration_args, regeneration_kwargs = regeneration_calls[0]
    assert regeneration_args[0]["risk_metrics"]["historical_var"] == 0.02
    assert regeneration_args[1] == "Unsafe original commentary."
    assert regeneration_args[2] == ["unsafe commentary"]
    assert regeneration_args[3] == []
    assert regeneration_args[4]
    assert regeneration_kwargs == {"use_llm": False}
    assert result.validation_result.passed is True
    assert result.llm_commentary.startswith("Regenerated commentary")
    assert [entry.tool_name for entry in result.execution_trace] == [
        "parse_portfolio",
        "validate_portfolio",
        "calculate_risk_metrics",
        "retrieve_methodology",
        "generate_commentary",
        "validate_report",
        "regenerate_commentary_with_validation_errors",
        "validate_report",
    ]


def test_validation_failure_after_retry_returns_final_failed_result():
    validation_calls = 0
    regeneration_calls = 0

    def always_fail_validation(*args):
        nonlocal validation_calls
        validation_calls += 1
        return ValidationResult(False, [], ["still invalid"], ["review commentary"])

    def regenerate(*args, **kwargs):
        nonlocal regeneration_calls
        regeneration_calls += 1
        return "Regenerated but still invalid commentary."

    replacements = {
        "calculate_risk_metrics": _fake_generate_portfolio_risk_report,
        "generate_commentary": lambda *args, **kwargs: "Initial invalid commentary.",
        "validate_report": always_fail_validation,
        "regenerate_commentary_with_validation_errors": regenerate,
    }
    tools = [
        replace(tool, handler=replacements[tool.name])
        if tool.name in replacements
        else tool
        for tool in list_registered_tools()
    ]

    result = run_risk_workflow(
        "40% SPY, 60% QQQ",
        use_llm=False,
        tool_executor=ToolExecutor(tools),
    )

    assert regeneration_calls == 1
    assert validation_calls == 2
    assert result.validation_result.passed is False
    assert result.validation_result.errors == ["still invalid"]
    assert [entry.tool_name for entry in result.execution_trace[-3:]] == [
        "validate_report",
        "regenerate_commentary_with_validation_errors",
        "validate_report",
    ]
