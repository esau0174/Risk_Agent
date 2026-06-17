from __future__ import annotations

from src.report_validator import ValidationCheck, ValidationResult
from src.workflow import (
    AgentRunResult,
    ExecutionTraceEntry,
    WorkflowPlan,
    WorkflowResult,
    WorkflowStep,
)
from src.workflow import presentation


def _workflow_result(route: str) -> WorkflowResult:
    is_market = route == "market_risk"
    validation = ValidationResult(
        passed=True,
        checks=[ValidationCheck("safe_output", True, "Output is valid.")],
        errors=[],
        warnings=[],
    )
    return WorkflowResult(
        query=f"Analyze {route}",
        plan=WorkflowPlan(
            objective=f"Run {route}",
            steps=[
                WorkflowStep(
                    name="validate_report",
                    description="Validate report.",
                    status="completed",
                    tool_name="validate_report",
                    output_summary="Validation passed.",
                )
            ],
        ),
        execution_trace=[
            ExecutionTraceEntry(
                step_number=1,
                tool_name=(
                    "calculate_risk_metrics" if is_market else "calculate_pfe_metrics"
                ),
                status="success",
                input_summary=f"{route} inputs.",
                output_summary=f"{route} outputs.",
                error=None,
            ),
            ExecutionTraceEntry(
                step_number=2,
                tool_name="validate_report",
                status="success",
                input_summary="Generated report.",
                output_summary="Validation passed.",
                error=None,
            ),
        ],
        active_modules=["shared", route],
        parsed_portfolio=(
            {"tickers": ["SPY"], "weights": [1.0]} if is_market else None
        ),
        risk_report=(
            {
                "risk_metrics": {
                    "annualized_volatility": 0.2671,
                    "historical_var": 0.0232,
                    "expected_shortfall": 0.0347,
                    "max_drawdown": 0.2377,
                }
            }
            if is_market
            else None
        ),
        pfe_result=(
            None
            if is_market
            else {
                "peak_pfe_95": 2_100_000.0,
                "peak_pfe_99": 2_600_000.0,
                "epe": 1_080_000.0,
                "largest_netting_set_by_peak_pfe": "NS-001",
                "configured_limit": 2_500_000.0,
                "limit_utilization": 0.84,
                "limit_status": "PASSED",
            }
        ),
        stress_test_results=(
            [{"portfolio_loss_pct": 0.225}] if is_market else []
        ),
        methodology_notes=[],
        llm_commentary=f"Final {route} commentary.",
        validation_result=validation,
        warnings=[],
    )


def test_full_workflow_returns_structured_agent_run_result(monkeypatch):
    results = iter([_workflow_result("market_risk"), _workflow_result("credit_risk")])
    monkeypatch.setattr(presentation, "run_risk_workflow", lambda *args, **kwargs: next(results))

    result = presentation.run_full_risk_agent_workflow(
        market_query="Analyze market risk",
        market_data_file="portfolio.csv",
        credit_query="Analyze credit risk",
        credit_data_file="exposure.csv",
        config_file="risk_config.json",
    )

    assert isinstance(result, AgentRunResult)
    assert isinstance(result.user_report, str)
    assert "Combined Executive Summary" in result.user_report
    assert "95% historical VaR: 2.32%" in result.user_report
    assert "Peak 95% PFE: USD 2,100,000.00" in result.user_report
    assert "Peak 99% PFE: USD 2,600,000.00" in result.user_report
    assert "EPE: USD 1,080,000.00" in result.user_report
    assert "Limit utilization: 84.00% of USD 2,500,000.00" in result.user_report
    assert "Limit status: PASSED" in result.user_report
    assert "Regulatory Risk" in result.user_report
    assert "SA-CCR readiness: WARNING" in result.user_report
    assert "SIMM / RegIM readiness: WARNING" in result.user_report
    assert "Regulatory capital calculation: Not performed" in result.user_report
    assert "SA-CCR missing inputs: trade_type, notional" in result.user_report
    assert "SIMM / RegIM available inputs: none" in result.user_report
    assert "SIMM / RegIM missing inputs: risk_class" in result.user_report
    assert "Validation: PASSED" in result.user_report
    assert len(result.execution_trace) == 5
    assert all(isinstance(entry, dict) for entry in result.execution_trace)
    assert {entry["workflow"] for entry in result.execution_trace} == {
        "market_risk",
        "credit_risk",
        "regulatory_risk",
    }
    assert result.validation_result["passed"] is True
    assert result.validation_result["market_risk"]["passed"] is True
    assert result.validation_result["regulatory_risk"]["passed"] is True
    assert result.raw_outputs["market_risk"]["risk_report"] is not None
    assert result.raw_outputs["credit_risk"]["pfe_result"] is not None
    assert result.raw_outputs["regulatory_risk"]["overall_status"] == "WARNING"


def test_combined_trace_preserves_credit_exposure_loading_display_name():
    market_result = _workflow_result("market_risk")
    credit_result = _workflow_result("credit_risk")
    credit_result.execution_trace.insert(
        0,
        ExecutionTraceEntry(
            step_number=1,
            tool_name="load_exposure_profile",
            status="success",
            input_summary="Structured exposure profile file.",
            output_summary="Loaded exposure profile rows.",
            error=None,
        ),
    )

    trace = presentation._combine_execution_traces(
        market_result,
        credit_result,
        {"missing_inputs": []},
    )
    credit_tools = [
        entry["tool_name"]
        for entry in trace
        if entry["workflow"] == "credit_risk"
    ]

    assert credit_tools[0] == "load_exposure_profile"
    assert "load_portfolio_file" not in credit_tools
