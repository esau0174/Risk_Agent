from __future__ import annotations

from dataclasses import replace

from src.tool_executor import ToolExecutor
from src.tool_registry import list_registered_tools
from src.workflow import WorkflowResult, build_risk_workflow_plan, run_risk_workflow


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
    def fake_generate_portfolio_risk_report(
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

    tools = [
        replace(tool, callable=fake_generate_portfolio_risk_report)
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
    assert result.warnings == [
        "LLM commentary disabled; returned deterministic fallback commentary."
    ]
