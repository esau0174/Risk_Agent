from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.core.tool_executor import ToolExecutor
from src.data.portfolio_loader import ExposureProfile
from src.knowledge.rag import load_methodology_docs
from src.reporting.agent import _build_methodology_query
from src.workflow.context import WorkflowExecutionContext
from src.workflow.engine import PFE_METHODOLOGY_TITLES
from src.workflow.types import WorkflowPlan


SUPPORTED_DIRECT_TOOLS = {
    "load_portfolio_file",
    "load_exposure_profile",
    "validate_portfolio",
    "load_risk_config",
    "calculate_risk_metrics",
    "run_stress_test",
    "calculate_pfe_metrics",
    "assess_regulatory_readiness",
    "load_sensitivity_file",
    "validate_sensitivity_file",
    "aggregate_greeks",
    "retrieve_methodology",
    "generate_commentary",
    "validate_report",
}


class PlanExecutionNotSupported(RuntimeError):
    """Raised when an approved plan cannot yet be executed directly."""


@dataclass
class ApprovedPlanExecutor:
    """Sequential executor for already-validated workflow plans."""

    tool_executor: ToolExecutor | None = None

    def __post_init__(self) -> None:
        if self.tool_executor is None:
            self.tool_executor = ToolExecutor()

    def can_execute(self, plan: WorkflowPlan, context: WorkflowExecutionContext) -> bool:
        tool_names = [step.tool_name for step in plan.steps]
        if any(tool_name not in SUPPORTED_DIRECT_TOOLS for tool_name in tool_names):
            return False
        if context.selected_route == "regulatory" and any(
            tool_name != "assess_regulatory_readiness" for tool_name in tool_names
        ):
            return False
        if "load_portfolio_file" in tool_names and context.selected_route not in {
            "market",
            "full",
        }:
            return False
        if "load_exposure_profile" in tool_names and context.selected_route not in {
            "credit",
            "full",
        }:
            return False
        if "load_sensitivity_file" in tool_names and context.selected_route not in {
            "sensitivity",
            "full",
        }:
            return False
        return True

    def execute(
        self,
        plan: WorkflowPlan,
        context: WorkflowExecutionContext,
    ) -> WorkflowExecutionContext:
        if not self.can_execute(plan, context):
            raise PlanExecutionNotSupported(
                "Approved plan cannot be executed directly by the lightweight plan executor."
            )

        for step in plan.steps:
            self._execute_step(step.tool_name, context)

        return context

    def _execute_step(
        self,
        tool_name: str,
        context: WorkflowExecutionContext,
    ) -> None:
        adapter = _ADAPTERS.get(tool_name)
        if adapter is None:
            raise PlanExecutionNotSupported(
                f"Tool '{tool_name}' is not mapped for direct plan execution."
            )

        input_summary = _input_summary(tool_name, context)
        warnings_before = len(context.warnings)
        try:
            adapter(self, context)
            status = "success"
            error = None
        except Exception as exc:
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            output_summary = _output_summary(tool_name, context)
            context.execution_trace.append(
                {
                    "step_number": len(context.execution_trace) + 1,
                    "tool_name": tool_name,
                    "status": status,
                    "inputs_summary": input_summary,
                    "input_summary": input_summary,
                    "outputs_summary": output_summary,
                    "output_summary": output_summary,
                    "warnings": context.warnings[warnings_before:],
                    "error": error,
                }
            )

    def _run_tool(self, tool_name: str, *args, **kwargs) -> Any:
        result = self.tool_executor.execute(tool_name, *args, **kwargs)
        if result.status != "success":
            raise RuntimeError(result.error)
        return result.output


def _load_portfolio_file(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    file_path = context.credit_data_file if context.selected_route == "credit" else context.market_data_file
    if file_path is None:
        raise PlanExecutionNotSupported("No structured data file is available.")
    loaded = executor._run_tool("load_portfolio_file", file_path)
    if isinstance(loaded, ExposureProfile):
        context.exposure_profile = loaded
    else:
        context.loaded_portfolio = loaded


def _load_exposure_profile(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.credit_data_file is None:
        raise PlanExecutionNotSupported("No exposure profile file is available.")
    loaded = executor._run_tool("load_exposure_profile", context.credit_data_file)
    if not isinstance(loaded, ExposureProfile):
        raise PlanExecutionNotSupported(
            "Structured credit input did not load as an exposure profile."
        )
    context.exposure_profile = loaded


def _validate_portfolio(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.loaded_portfolio is None:
        raise PlanExecutionNotSupported("Portfolio data is required before validation.")
    tickers = context.loaded_portfolio["tickers"]
    weights = executor._run_tool(
        "validate_portfolio",
        tickers,
        context.loaded_portfolio["weights"],
    )
    normalized_weights = weights.tolist() if hasattr(weights, "tolist") else list(weights)
    portfolio_metadata = context.loaded_portfolio.get("metadata")
    context.loaded_portfolio = {
        "tickers": tickers,
        "weights": normalized_weights,
    }
    if portfolio_metadata:
        context.loaded_portfolio["metadata"] = portfolio_metadata


def _load_risk_config(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    context.risk_config = executor._run_tool("load_risk_config", context.config_file)


def _calculate_risk_metrics(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.loaded_portfolio is None or context.risk_config is None:
        raise PlanExecutionNotSupported("Portfolio and risk configuration are required.")
    kwargs = {}
    if context.loaded_portfolio.get("metadata"):
        kwargs["portfolio_metadata"] = context.loaded_portfolio["metadata"]
    context.risk_report = executor._run_tool(
        "calculate_risk_metrics",
        context.loaded_portfolio["tickers"],
        context.loaded_portfolio["weights"],
        start_date=context.risk_config.market_data.start_date,
        end_date=context.risk_config.market_data.end_date,
        risk_config=context.risk_config,
        **kwargs,
    )


def _run_stress_test(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.loaded_portfolio is None or context.risk_config is None:
        raise PlanExecutionNotSupported("Portfolio and risk configuration are required.")
    kwargs = {}
    metadata = context.loaded_portfolio.get("metadata") or {}
    if metadata.get("total_notional_usd") is not None:
        kwargs["portfolio_notional_usd"] = metadata["total_notional_usd"]
    context.stress_test_results = executor._run_tool(
        "run_stress_test",
        context.loaded_portfolio["tickers"],
        context.loaded_portfolio["weights"],
        risk_config=context.risk_config,
        **kwargs,
    )


def _calculate_pfe_metrics(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.exposure_profile is None or context.risk_config is None:
        raise PlanExecutionNotSupported("Exposure profile and risk configuration are required.")
    context.pfe_result = executor._run_tool(
        "calculate_pfe_metrics",
        context.exposure_profile,
        credit_limits=context.risk_config.credit_limits,
    )


def _assess_regulatory_readiness(
    executor: ApprovedPlanExecutor,
    context: WorkflowExecutionContext,
) -> None:
    inputs = {
        "portfolio_weights": "available" if context.loaded_portfolio else None,
        "historical_market_data": "available" if context.risk_report else None,
        "exposure_profile": "available" if context.exposure_profile else None,
    }
    portfolio_metadata = (
        context.loaded_portfolio.get("metadata", {})
        if context.loaded_portfolio
        else {}
    )
    if portfolio_metadata.get("total_notional_usd") is not None:
        inputs["portfolio_notional_usd"] = portfolio_metadata["total_notional_usd"]
    if portfolio_metadata.get("asset_classes"):
        inputs["portfolio_asset_classes"] = portfolio_metadata["asset_classes"]
    if context.sensitivity_records is not None:
        inputs["precomputed_sensitivities"] = "available"
        inputs["sensitivity_fields"] = [
            "risk_class",
            "risk_factor",
            "bucket",
            "delta",
            "gamma",
            "vega",
            "theta",
            "currency",
        ]
    if context.sensitivity_result is not None:
        inputs["sensitivity_result"] = "available"
    context.regulatory_readiness = executor._run_tool(
        "assess_regulatory_readiness",
        inputs,
    )


def _load_sensitivity_file(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.sensitivity_data_file is None:
        raise PlanExecutionNotSupported("No sensitivity file is available.")
    context.sensitivity_records = executor._run_tool(
        "load_sensitivity_file",
        context.sensitivity_data_file,
    )


def _validate_sensitivity_file(
    executor: ApprovedPlanExecutor,
    context: WorkflowExecutionContext,
) -> None:
    if context.sensitivity_records is None:
        raise PlanExecutionNotSupported("Sensitivity records are required before validation.")
    context.sensitivity_records = executor._run_tool(
        "validate_sensitivity_file",
        context.sensitivity_records,
    )


def _aggregate_greeks(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.sensitivity_records is None:
        raise PlanExecutionNotSupported("Sensitivity records are required before aggregation.")
    context.sensitivity_result = executor._run_tool(
        "aggregate_greeks",
        context.sensitivity_records,
    )


def _retrieve_methodology(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    docs = load_methodology_docs()
    retrieved_notes: list[dict] = []
    if context.risk_report is not None:
        market_query = _build_methodology_query(context.user_query, context.risk_report)
        context.market_methodology_notes = executor._run_tool(
            "retrieve_methodology",
            market_query,
            docs,
            top_k=4,
        )
        retrieved_notes.extend(context.market_methodology_notes)

    if context.pfe_result is not None or context.selected_route == "credit":
        credit_docs = [doc for doc in docs if doc["title"] in PFE_METHODOLOGY_TITLES]
        credit_query = (
            f"{context.user_query} potential future exposure PFE expected exposure "
            "EPE netting set counterparty exposure limitations"
        )
        context.credit_methodology_notes = executor._run_tool(
            "retrieve_methodology",
            credit_query,
            credit_docs,
            top_k=4,
        )
        retrieved_notes.extend(context.credit_methodology_notes)

    if not retrieved_notes and context.regulatory_readiness is not None:
        query = f"{context.user_query} regulatory readiness limitations"
        retrieved_notes = executor._run_tool(
            "retrieve_methodology",
            query,
            docs,
            top_k=4,
        )
    else:
        seen = set()
        unique_notes = []
        for note in retrieved_notes:
            key = (note.get("title"), note.get("path"))
            if key in seen:
                continue
            seen.add(key)
            unique_notes.append(note)
        retrieved_notes = unique_notes
    context.methodology_notes = retrieved_notes


def _generate_commentary(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    commentary_parts = []
    if context.risk_report is not None:
        kwargs = {}
        if context.stress_test_results:
            kwargs["stress_results"] = context.stress_test_results
        context.market_commentary = executor._run_tool(
            "generate_commentary",
            context.user_query,
            context.risk_report,
            context.market_methodology_notes or context.methodology_notes,
            use_llm=context.use_llm,
            **kwargs,
        )
        commentary_parts.append(context.market_commentary)

    if context.pfe_result is not None:
        context.credit_commentary = executor._run_tool(
            "generate_commentary",
            context.user_query,
            None,
            context.credit_methodology_notes or context.methodology_notes,
            use_llm=context.use_llm,
            pfe_result=context.pfe_result,
        )
        commentary_parts.append(context.credit_commentary)

    if context.regulatory_readiness is not None:
        context.regulatory_commentary = ""

    context.combined_commentary = "\n\n".join(part for part in commentary_parts if part)
    context.commentary = context.combined_commentary or None
    if not context.use_llm:
        context.warnings.append(
            "LLM commentary disabled; returned deterministic fallback commentary."
        )


def _validate_report(executor: ApprovedPlanExecutor, context: WorkflowExecutionContext) -> None:
    if context.risk_report is not None:
        kwargs = {}
        if context.stress_test_results:
            kwargs["stress_results"] = context.stress_test_results
        context.market_validation_result = executor._run_tool(
            "validate_report",
            context.loaded_portfolio,
            context.risk_report,
            context.market_methodology_notes or context.methodology_notes,
            context.market_commentary or "",
            **kwargs,
        )

    if context.pfe_result is not None:
        context.credit_validation_result = executor._run_tool(
            "validate_report",
            None,
            None,
            context.credit_methodology_notes or context.methodology_notes,
            context.credit_commentary or "",
            pfe_result=context.pfe_result,
        )

    context.report_validation_result = (
        context.credit_validation_result
        or context.market_validation_result
    )


_ADAPTERS: dict[str, Callable[[ApprovedPlanExecutor, WorkflowExecutionContext], None]] = {
    "load_portfolio_file": _load_portfolio_file,
    "load_exposure_profile": _load_exposure_profile,
    "validate_portfolio": _validate_portfolio,
    "load_risk_config": _load_risk_config,
    "calculate_risk_metrics": _calculate_risk_metrics,
    "run_stress_test": _run_stress_test,
    "calculate_pfe_metrics": _calculate_pfe_metrics,
    "assess_regulatory_readiness": _assess_regulatory_readiness,
    "load_sensitivity_file": _load_sensitivity_file,
    "validate_sensitivity_file": _validate_sensitivity_file,
    "aggregate_greeks": _aggregate_greeks,
    "retrieve_methodology": _retrieve_methodology,
    "generate_commentary": _generate_commentary,
    "validate_report": _validate_report,
}


def _input_summary(tool_name: str, context: WorkflowExecutionContext) -> str:
    if tool_name == "load_portfolio_file":
        return f"route={context.selected_route}; market portfolio file"
    if tool_name == "load_exposure_profile":
        return "counterparty exposure profile file"
    if tool_name == "validate_portfolio":
        return "loaded portfolio holdings"
    if tool_name == "load_risk_config":
        return context.config_file or "default risk configuration"
    if tool_name == "calculate_risk_metrics":
        return "validated portfolio and risk configuration"
    if tool_name == "run_stress_test":
        return "validated portfolio and configured stress scenarios"
    if tool_name == "calculate_pfe_metrics":
        return "exposure profile and credit limits"
    if tool_name == "assess_regulatory_readiness":
        return "available workflow inputs"
    if tool_name == "load_sensitivity_file":
        return "precomputed Greeks sensitivity file"
    if tool_name == "validate_sensitivity_file":
        return "loaded precomputed Greeks records"
    if tool_name == "aggregate_greeks":
        return "validated precomputed Greeks records"
    if tool_name == "retrieve_methodology":
        return "analysis query and local methodology documents"
    if tool_name == "generate_commentary":
        return "calculated facts and retrieved methodology"
    if tool_name == "validate_report":
        return "calculated facts, methodology, and commentary"
    return "workflow context"


def _output_summary(tool_name: str, context: WorkflowExecutionContext) -> str:
    if tool_name == "load_exposure_profile":
        if context.exposure_profile is not None:
            return f"loaded {len(context.exposure_profile.exposures)} exposure rows"
    if tool_name == "load_portfolio_file":
        if context.loaded_portfolio is not None:
            return f"loaded {len(context.loaded_portfolio['tickers'])} holdings"
    if tool_name == "validate_portfolio" and context.loaded_portfolio is not None:
        return "portfolio weights validated"
    if tool_name == "load_risk_config" and context.risk_config is not None:
        return "risk configuration loaded"
    if tool_name == "calculate_risk_metrics" and context.risk_report is not None:
        return "calculated " + ", ".join(context.risk_report["risk_metrics"].keys())
    if tool_name == "run_stress_test":
        return f"calculated {len(context.stress_test_results)} stress results"
    if tool_name == "calculate_pfe_metrics" and context.pfe_result is not None:
        return "calculated PFE and EPE metrics"
    if tool_name == "assess_regulatory_readiness" and context.regulatory_readiness is not None:
        return f"readiness status {context.regulatory_readiness['overall_status']}"
    if tool_name == "load_sensitivity_file" and context.sensitivity_records is not None:
        return f"loaded {len(context.sensitivity_records)} sensitivity records"
    if tool_name == "validate_sensitivity_file" and context.sensitivity_records is not None:
        return f"validated {len(context.sensitivity_records)} sensitivity records"
    if tool_name == "aggregate_greeks" and context.sensitivity_result is not None:
        return "aggregated supplied delta, gamma, vega, and theta"
    if tool_name == "retrieve_methodology":
        return f"retrieved {len(context.methodology_notes)} methodology notes"
    if tool_name == "generate_commentary" and context.commentary is not None:
        return f"generated commentary with {len(context.commentary)} characters"
    if tool_name == "validate_report" and context.report_validation_result is not None:
        return "report validation passed" if context.report_validation_result.passed else "report validation failed"
    return "no output recorded"
