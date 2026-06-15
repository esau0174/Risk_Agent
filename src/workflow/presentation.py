from __future__ import annotations

from dataclasses import asdict

from src.core.tool_executor import ToolExecutor
from src.validators.regulatory import validate_regulatory_readiness_report
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
        config_file=config_file,
        use_llm=use_llm,
    )
    regulatory_result = _assess_regulatory_readiness()
    user_report_for_validation = _build_user_report(
        market_result,
        credit_result,
        regulatory_result,
    )
    regulatory_validation = validate_regulatory_readiness_report(
        user_report_for_validation,
        regulatory_result,
    )
    user_report = _build_user_report(
        market_result,
        credit_result,
        regulatory_result,
        regulatory_validation,
    )

    return AgentRunResult(
        user_report=user_report,
        execution_trace=_combine_execution_traces(
            market_result,
            credit_result,
            regulatory_result,
        ),
        validation_result=_build_validation_result(
            market_result,
            credit_result,
            regulatory_validation,
        ),
        raw_outputs={
            "market_risk": asdict(market_result),
            "credit_risk": asdict(credit_result),
            "regulatory_risk": regulatory_result,
        },
    )


def _build_user_report(
    market_result: WorkflowResult,
    credit_result: WorkflowResult,
    regulatory_result: dict,
    regulatory_validation=None,
) -> str:
    market_metrics = market_result.risk_report["risk_metrics"]
    pfe_metrics = credit_result.pfe_result
    stress_loss = (
        market_result.stress_test_results[0]["portfolio_loss_pct"]
        if market_result.stress_test_results
        else None
    )

    lines = [
        "RiskFlow Agent - Full Risk Workflow Demo",
        "=======================================",
        "Combined Executive Summary",
        "Active modules covered: Market Risk, Credit Risk, Regulatory Risk",
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
            "Credit Risk",
            f"- Peak 95% PFE: USD {pfe_metrics['peak_pfe_95']:,.2f}",
        ]
    )
    if pfe_metrics.get("peak_pfe_99") is not None:
        lines.append(f"- Peak 99% PFE: USD {pfe_metrics['peak_pfe_99']:,.2f}")
    lines.extend(
        [
            f"- EPE: USD {pfe_metrics['epe']:,.2f}",
            (
                "- Largest netting set: "
                f"{pfe_metrics['largest_netting_set_by_peak_pfe']}"
            ),
            _limit_utilization_line(pfe_metrics),
            f"- Limit status: {pfe_metrics['limit_status']}",
            f"- Validation: {_validation_status(credit_result)}",
            "",
            "Regulatory Risk",
            f"- SA-CCR readiness: {regulatory_result['sa_ccr']['status']}",
            f"- SIMM / RegIM readiness: {regulatory_result['simm_regim']['status']}",
            (
                "- Regulatory capital calculation: "
                f"{regulatory_result['regulatory_capital_calculation']}"
            ),
            (
                "- SA-CCR missing inputs: "
                + ", ".join(regulatory_result["sa_ccr"]["missing_required_fields"])
            ),
            (
                "- SIMM / RegIM missing inputs: "
                + ", ".join(
                    regulatory_result["simm_regim"]["missing_required_fields"]
                )
            ),
            f"- Guardrail: {regulatory_result['guardrail']}",
            f"- Validation: {_regulatory_validation_status(regulatory_validation)}",
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
    regulatory_result: dict,
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
    combined_trace.append(
        {
            "step_number": len(combined_trace) + 1,
            "tool_name": "assess_regulatory_readiness",
            "status": "success",
            "input_summary": "Available market and credit demo inputs.",
            "output_summary": (
                "Assessed SA-CCR and SIMM / RegIM readiness; "
                f"{len(regulatory_result['missing_inputs'])} missing inputs."
            ),
            "error": None,
            "workflow": "regulatory_risk",
            "workflow_step_number": 1,
        }
    )
    return combined_trace


def _build_validation_result(
    market_result: WorkflowResult,
    credit_result: WorkflowResult,
    regulatory_validation,
) -> dict:
    return {
        "passed": (
            market_result.validation_result.passed
            and credit_result.validation_result.passed
            and regulatory_validation.passed
        ),
        "market_risk": asdict(market_result.validation_result),
        "credit_risk": asdict(credit_result.validation_result),
        "regulatory_risk": asdict(regulatory_validation),
    }


def _validation_status(result: WorkflowResult) -> str:
    return "PASSED" if result.validation_result.passed else "FAILED"


def _regulatory_validation_status(regulatory_validation) -> str:
    if regulatory_validation is None:
        return "NOT_RUN"
    return "PASSED" if regulatory_validation.passed else "FAILED"


def _limit_utilization_line(pfe_metrics: dict) -> str:
    if pfe_metrics.get("limit_utilization") is None:
        return "- Limit utilization: not available; no configured limit"
    return (
        f"- Limit utilization: {pfe_metrics['limit_utilization']:.2%} of "
        f"USD {pfe_metrics['configured_limit']:,.2f}"
    )


def _assess_regulatory_readiness() -> dict:
    result = ToolExecutor().execute(
        "assess_regulatory_readiness",
        {
            "portfolio_weights": "available",
            "historical_market_data": "available",
            "exposure_profile": "available",
        },
    )
    if result.status != "success":
        raise RuntimeError(
            f"Tool '{result.tool_name}' failed: {result.error}"
        )
    return result.output
