from __future__ import annotations

from dataclasses import asdict

from src.workflow.engine import run_risk_workflow
from src.workflow.types import AgentRunResult, WorkflowResult


def run_full_risk_agent_workflow(
    market_query: str,
    market_data_file: str,
    credit_query: str,
    credit_data_file: str,
    config_file: str | None = None,
    use_llm: bool = False,
) -> AgentRunResult:
    """Run market and credit workflows and return presentation-ready output."""
    market_result = run_risk_workflow(
        market_query,
        data_file=market_data_file,
        config_file=config_file,
        use_llm=use_llm,
    )
    credit_result = run_risk_workflow(
        credit_query,
        data_file=credit_data_file,
        use_llm=use_llm,
    )

    return AgentRunResult(
        user_report=_build_user_report(market_result, credit_result),
        execution_trace=_combine_execution_traces(market_result, credit_result),
        validation_result=_build_validation_result(market_result, credit_result),
        raw_outputs={
            "market_risk": asdict(market_result),
            "credit_risk": asdict(credit_result),
        },
    )


def _build_user_report(
    market_result: WorkflowResult,
    credit_result: WorkflowResult,
) -> str:
    market_metrics = market_result.risk_report["risk_metrics"]
    pfe_metrics = credit_result.pfe_result
    stress_loss = (
        market_result.stress_test_results[0]["portfolio_loss_pct"]
        if market_result.stress_test_results
        else None
    )

    lines = [
        "FinRisk Agent - Full Risk Workflow Demo",
        "=======================================",
        "Combined Executive Summary",
        "Active modules covered: Market Risk, Credit Risk",
        "",
        "Market Risk",
        f"- Annualized volatility: {market_metrics['annualized_volatility']:.2%}",
        f"- 95% historical VaR: {market_metrics['historical_var']:.2%}",
        f"- 95% Expected Shortfall: {market_metrics['expected_shortfall']:.2%}",
        f"- Maximum drawdown: {market_metrics['max_drawdown']:.2%}",
    ]
    if stress_loss is not None:
        lines.append(f"- Stress scenario loss: {stress_loss:.2%}")

    lines.extend(
        [
            f"- Validation: {_validation_status(market_result)}",
            "",
            "Credit Risk / PFE",
            f"- Peak 95% PFE: {pfe_metrics['peak_pfe_95']:,.2f}",
        ]
    )
    if pfe_metrics.get("peak_pfe_99") is not None:
        lines.append(f"- Peak 99% PFE: {pfe_metrics['peak_pfe_99']:,.2f}")
    lines.extend(
        [
            f"- EPE: {pfe_metrics['epe']:,.2f}",
            (
                "- Largest netting set: "
                f"{pfe_metrics['largest_netting_set_by_peak_pfe']}"
            ),
            f"- Validation: {_validation_status(credit_result)}",
            "",
            "Market Risk Commentary",
            market_result.llm_commentary,
            "",
            "Credit Risk Commentary",
            credit_result.llm_commentary,
        ]
    )
    return "\n".join(lines)


def _combine_execution_traces(
    market_result: WorkflowResult,
    credit_result: WorkflowResult,
) -> list[dict]:
    combined_trace = []
    for workflow_name, result in (
        ("market_risk", market_result),
        ("credit_risk", credit_result),
    ):
        for entry in result.execution_trace:
            trace_entry = asdict(entry)
            trace_entry["workflow"] = workflow_name
            trace_entry["workflow_step_number"] = trace_entry["step_number"]
            trace_entry["step_number"] = len(combined_trace) + 1
            combined_trace.append(trace_entry)
    return combined_trace


def _build_validation_result(
    market_result: WorkflowResult,
    credit_result: WorkflowResult,
) -> dict:
    return {
        "passed": (
            market_result.validation_result.passed
            and credit_result.validation_result.passed
        ),
        "market_risk": asdict(market_result.validation_result),
        "credit_risk": asdict(credit_result.validation_result),
    }


def _validation_status(result: WorkflowResult) -> str:
    return "PASSED" if result.validation_result.passed else "FAILED"
