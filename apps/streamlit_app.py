from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

import streamlit as st

from riskflow_agent import run_agent_workflow


PRESETS = {
    "Core Risk Review": (
        "Plan a Market Risk, Counterparty Risk, and Regulatory Risk review with "
        "stress testing, PFE exposure analysis, and regulatory readiness screening."
    ),
    "Market + Sensitivity + Regulatory Risk": (
        "Run market risk, sensitivity risk, and regulatory risk review."
    ),
    "SIMM Readiness from Sensitivities": (
        "Check SIMM readiness using Greeks sensitivities."
    ),
}

PRESET_DESCRIPTIONS = {
    "Core Risk Review": "Market + Counterparty + Regulatory + Stress",
    "Market + Sensitivity + Regulatory Risk": (
        "Greeks aggregation feeding SIMM readiness"
    ),
    "SIMM Readiness from Sensitivities": "Focused regulatory-readiness workflow",
}

STATUS_LABELS = {
    "PASSED": "Passed",
    "WARNING": "Warning",
    "FAILED": "Failed",
    "NOT_RUN": "Not requested",
    "READY": "Ready",
    "PARTIAL": "Partial",
    "NOT_READY": "Not ready",
}

TOOL_LABELS = {
    "load_portfolio_file": "Load market portfolio",
    "load_exposure_profile": "Load exposure profile",
    "load_sensitivity_file": "Load sensitivities",
    "validate_portfolio": "Validate portfolio",
    "load_risk_config": "Load risk config",
    "calculate_risk_metrics": "Calculate market risk metrics",
    "run_stress_test": "Run stress test",
    "calculate_pfe_metrics": "Calculate PFE metrics",
    "validate_sensitivity_file": "Validate sensitivity file",
    "aggregate_greeks": "Aggregate Greeks",
    "assess_regulatory_readiness": "Assess regulatory readiness",
    "retrieve_methodology": "Retrieve methodology",
    "generate_commentary": "Generate commentary",
    "validate_report": "Validate report",
    "regenerate_commentary_with_validation_errors": "Regenerate commentary",
}


def main() -> None:
    st.set_page_config(page_title="RiskFlow Agent", layout="wide")
    st.title("RiskFlow Agent")
    st.caption("Interactive inspection view over the structured agent workflow result.")

    with st.sidebar:
        st.header("Workflow")
        preset_name = st.selectbox("Workflow preset", list(PRESETS))
        st.caption(PRESET_DESCRIPTIONS[preset_name])
        planner_mode = st.selectbox("Planner mode", ["rule", "auto", "llm"], index=0)
        request_text = st.text_area(
            "Request",
            value=PRESETS[preset_name],
            height=150,
        )
        show_raw_outputs = st.checkbox("Show raw outputs", value=False)
        run_analysis = st.button("Run Analysis", type="primary")

    if not run_analysis:
        st.info("Choose a workflow preset and click Run Analysis.")
        return

    try:
        with st.spinner("Running RiskFlow Agent workflow..."):
            result = run_agent_workflow(
                query=request_text,
                planner_mode=planner_mode,
            )
    except Exception as exc:
        st.error(f"Unable to run RiskFlow Agent workflow: {exc}")
        return

    _render_status_cards(result, planner_mode)
    _render_tabs(result, show_raw_outputs, planner_mode)


def _render_status_cards(result, requested_planner_mode: str) -> None:
    validation_status = _overall_validation_status(result.validation_result)
    plan_status = "PASSED" if result.plan_validation_result.passed else "FAILED"
    selected_route = result.orchestration_trace.get("selected_route") or "none"
    planner_display = _planner_display(requested_planner_mode, result.planner_mode)

    cols = st.columns(4)
    cols[0].metric("Planner", planner_display)
    cols[1].metric("Selected route", _display_route(selected_route))
    cols[2].metric("Plan validation", _status_label(plan_status))
    cols[3].metric("Overall validation", _status_label(validation_status))

    if result.planner_warnings:
        st.warning("Planner note: " + " ".join(result.planner_warnings))
    if result.orchestration_trace.get("execution_mode") == "deterministic_route_fallback":
        st.info(
            "Execution path note: The planner proposed an approved workflow plan. "
            "The approved plan was mapped to a controlled deterministic route for "
            "reproducible execution."
        )
    if not result.plan_validation_result.passed:
        st.error(result.planner_message)


def _render_tabs(result, show_raw_outputs: bool, requested_planner_mode: str) -> None:
    tab_names = [
        "Executive Report",
        "Agent Plan",
        "Validation & Guardrails",
        "Execution Trace",
    ]
    if show_raw_outputs:
        tab_names.append("Raw Outputs")

    tabs = st.tabs(tab_names)
    with tabs[0]:
        _render_executive_report(result)
    with tabs[1]:
        _render_agent_plan(result, requested_planner_mode)
    with tabs[2]:
        _render_validation(result)
    with tabs[3]:
        _render_execution_trace(result)
    if show_raw_outputs:
        with tabs[4]:
            _render_raw_outputs(result)


def _render_executive_report(result) -> None:
    st.subheader("Executive Report")
    st.caption("Business-facing report generated from deterministic workflow outputs.")

    _render_executive_status_cards(result)

    sections = _split_report_sections(result.user_report or result.final_report_summary)
    if not sections:
        _render_readable_markdown(result.user_report or result.final_report_summary)
        return

    module_order = [
        "Market Risk",
        "Counterparty Risk",
        "Sensitivity Risk",
        "Regulatory Risk",
        "Commentary / Assumptions",
    ]
    rendered = set()
    for title in module_order:
        matching_sections = [
            section for section in sections if section["display_title"] == title
        ]
        if not matching_sections:
            continue
        rendered.add(title)
        with st.expander(title, expanded=title != "Commentary / Assumptions"):
            _render_module_metric_cards(title, result)
            for section in matching_sections:
                _render_readable_markdown(section["content"])

    remaining = [
        section for section in sections if section["display_title"] not in rendered
    ]
    for section in remaining:
        with st.expander(section["display_title"], expanded=False):
            _render_readable_markdown(section["content"])


def _render_agent_plan(result, requested_planner_mode: str) -> None:
    st.subheader("Agent Plan")
    st.caption("Auditable orchestration evidence. This is not hidden chain-of-thought.")
    trace = result.orchestration_trace
    st.info(
        "Planner source and execution path are separate controls: the planner proposes "
        "tools, the validator approves supported steps, and execution may use either "
        "the approved-plan executor or a deterministic route fallback. See Execution "
        "Trace for the tools that actually ran."
    )

    summary_cols = st.columns(4)
    summary_cols[0].metric(
        "Planner",
        _planner_display(requested_planner_mode, result.planner_mode),
    )
    summary_cols[1].metric(
        "Selected route",
        _display_route(trace.get("selected_route") or "none"),
    )
    summary_cols[2].metric(
        "Execution mode",
        _display_execution_mode(trace.get("execution_mode", "unknown")),
    )
    summary_cols[3].metric(
        "Plan validation",
        _status_label("PASSED" if result.plan_validation_result.passed else "FAILED"),
    )

    approved_steps = _approved_tool_rows(result.approved_plan)
    if approved_steps:
        st.write("Approved tool sequence")
        st.dataframe(approved_steps, use_container_width=True, hide_index=True)
    else:
        st.info("No approved tool sequence. Execution was not started.")

    skipped_tools = _clean_tool_names(trace.get("skipped_or_unsupported_tools"))
    st.write("Skipped / unsupported tools")
    st.write(", ".join(skipped_tools) if skipped_tools else "none")

    route_mapping_note = trace.get("route_mapping_note")
    if route_mapping_note:
        st.info(route_mapping_note)
    if trace.get("execution_mode") == "deterministic_route_fallback":
        st.info(
            "The approved plan was intentionally mapped to a controlled deterministic "
            "route for reproducible execution."
        )

    if result.plan_validation_result.errors:
        st.error("; ".join(result.plan_validation_result.errors))
    if result.plan_validation_result.warnings:
        st.warning("; ".join(result.plan_validation_result.warnings))


def _render_validation(result) -> None:
    st.subheader("Validation & Guardrails")
    validation_result = result.validation_result
    overall = _overall_validation_status(validation_result)
    if overall == "PASSED":
        st.success("Overall validation: Passed")
    elif overall == "WARNING":
        st.warning("Overall validation: Warning")
    else:
        st.error(f"Overall validation: {_status_label(overall)}")

    domain_rows = _domain_validation_rows(validation_result)
    if domain_rows:
        st.write("Domain validation")
        st.dataframe(domain_rows, use_container_width=True, hide_index=True)

    checks = _validation_checks(validation_result)
    if checks:
        st.write("Validation checks")
        st.dataframe(checks, use_container_width=True, hide_index=True)

    warnings = _validation_messages(validation_result, "warnings")
    errors = _validation_messages(validation_result, "errors")
    if warnings:
        with st.expander("Warnings", expanded=True):
            for warning in warnings:
                st.warning(warning)
    if errors:
        with st.expander("Errors", expanded=True):
            for error in errors:
                st.error(error)


def _render_execution_trace(result) -> None:
    st.subheader("Execution Trace")
    trace = result.orchestration_trace
    cols = st.columns(2)
    cols[0].metric(
        "Execution mode",
        _display_execution_mode(trace.get("execution_mode", "unknown")),
    )
    cols[1].metric("Selected route", _display_route(trace.get("selected_route") or "none"))
    entries = _execution_trace_rows(result.execution_trace)
    if entries:
        st.dataframe(entries, use_container_width=True, hide_index=True)
    else:
        st.info("No tools were executed.")


def _render_raw_outputs(result) -> None:
    st.subheader("Raw Outputs")
    st.caption("Structured workflow outputs only; no hidden chain-of-thought.")
    with st.expander("Raw analytics outputs", expanded=False):
        st.json(_to_jsonable(result.raw_outputs))
    with st.expander("Orchestration trace", expanded=False):
        st.json(_to_jsonable(result.orchestration_trace))
    with st.expander("Validation result", expanded=False):
        st.json(_to_jsonable(result.validation_result))


def _approved_tool_rows(plan) -> list[dict[str, Any]]:
    if plan is None:
        return []
    return [
        {
            "step": index,
            "tool": _display_tool_name(step.tool_name),
            "description": step.description,
        }
        for index, step in enumerate(plan.steps, start=1)
    ]


def _domain_validation_rows(validation_result) -> list[dict[str, str]]:
    if not isinstance(validation_result, dict):
        return []

    labels = {
        "market_risk": "Market Risk",
        "credit_risk": "Counterparty Risk",
        "sensitivity_risk": "Sensitivity Risk",
        "regulatory_risk": "Regulatory Risk",
    }
    rows = []
    for key, label in labels.items():
        domain_result = validation_result.get(key)
        if isinstance(domain_result, dict):
            rows.append(
                {
                    "Domain": label,
                    "Status": _status_label(
                        "PASSED" if domain_result.get("passed") else "FAILED"
                    ),
                }
            )
    return rows


def _validation_checks(validation_result) -> list[dict[str, Any]]:
    checks = getattr(validation_result, "checks", None)
    if not checks:
        return []
    return [
        {
            "Check": getattr(check, "name", ""),
            "Status": _status_label(
                "PASSED" if getattr(check, "passed", False) else "FAILED"
            ),
            "Message": getattr(check, "message", ""),
        }
        for check in checks
    ]


def _validation_messages(validation_result, attribute: str) -> list[str]:
    if validation_result is None:
        return []
    if isinstance(validation_result, dict):
        messages = validation_result.get(attribute, [])
        return list(messages) if isinstance(messages, list) else []
    messages = getattr(validation_result, attribute, [])
    return list(messages) if messages else []


def _overall_validation_status(validation_result) -> str:
    if validation_result is None:
        return "NOT_RUN"
    if isinstance(validation_result, dict):
        return "PASSED" if validation_result.get("passed") else "FAILED"
    return "PASSED" if getattr(validation_result, "passed", False) else "FAILED"


def _render_executive_status_cards(result) -> None:
    rows = _domain_validation_rows(result.validation_result)
    statuses = {row["Domain"]: row["Status"] for row in rows}
    labels = [
        "Overall validation",
        "Market Risk",
        "Counterparty Risk",
        "Sensitivity Risk",
        "Regulatory Risk",
    ]
    values = {
        "Overall validation": _overall_validation_status(result.validation_result),
        **statuses,
    }
    cols = st.columns(len(labels))
    for column, label in zip(cols, labels):
        column.metric(label, _status_label(values.get(label, "NOT_RUN")))


def _render_module_metric_cards(title: str, result) -> None:
    cards = {
        "Market Risk": _market_metric_cards(result),
        "Counterparty Risk": _counterparty_metric_cards(result),
        "Regulatory Risk": _regulatory_metric_cards(result),
    }.get(title, [])
    if not cards:
        return

    cols = st.columns(len(cards))
    for column, card in zip(cols, cards):
        column.metric(card["label"], card["value"])


def _market_metric_cards(result) -> list[dict[str, str]]:
    market = _raw_output_section(result, "market_risk")
    risk_report = _get_value(market, "risk_report") or market
    metrics = _get_value(risk_report, "risk_metrics") or {}
    dollar_metrics = _get_value(risk_report, "dollar_risk_metrics") or {}
    stress_results = _get_value(market, "stress_test_results") or []
    stress_result = stress_results[0] if stress_results else {}

    cards: list[dict[str, str]] = []
    if _get_value(metrics, "historical_var") is not None:
        cards.append(
            {
                "label": "95% VaR",
                "value": _format_percent(_get_value(metrics, "historical_var")),
            }
        )
    if _get_value(dollar_metrics, "dollar_historical_var") is not None:
        cards.append(
            {
                "label": "Dollar VaR",
                "value": _format_usd(
                    _get_value(dollar_metrics, "dollar_historical_var")
                ),
            }
        )
    if _get_value(metrics, "expected_shortfall") is not None:
        cards.append(
            {
                "label": "Expected Shortfall",
                "value": _format_percent(_get_value(metrics, "expected_shortfall")),
            }
        )
    if _get_value(stress_result, "portfolio_loss_pct") is not None:
        cards.append(
            {
                "label": "Stress Loss",
                "value": _format_percent(_get_value(stress_result, "portfolio_loss_pct")),
            }
        )
    return cards


def _counterparty_metric_cards(result) -> list[dict[str, str]]:
    credit = _raw_output_section(result, "credit_risk")
    cards: list[dict[str, str]] = []
    if _get_value(credit, "peak_pfe_95") is not None:
        cards.append(
            {"label": "Peak 95% PFE", "value": _format_usd(_get_value(credit, "peak_pfe_95"))}
        )
    if _get_value(credit, "peak_pfe_99") is not None:
        cards.append(
            {"label": "Peak 99% PFE", "value": _format_usd(_get_value(credit, "peak_pfe_99"))}
        )
    if _get_value(credit, "average_expected_exposure") is not None:
        cards.append(
            {
                "label": "EPE",
                "value": _format_usd(_get_value(credit, "average_expected_exposure")),
            }
        )
    if _get_value(credit, "limit_utilization") is not None:
        cards.append(
            {
                "label": "Limit Utilization",
                "value": _format_percent(_get_value(credit, "limit_utilization")),
            }
        )
    return cards


def _regulatory_metric_cards(result) -> list[dict[str, str]]:
    regulatory = _raw_output_section(result, "regulatory_risk")
    if not regulatory:
        return []
    return [
        {
            "label": "SA-CCR readiness",
            "value": _status_label(_get_value(_get_value(regulatory, "sa_ccr") or {}, "status")),
        },
        {
            "label": "SIMM / RegIM readiness",
            "value": _status_label(
                _get_value(_get_value(regulatory, "simm_regim") or {}, "status")
            ),
        },
        {
            "label": "Capital calculation",
            "value": str(_get_value(regulatory, "regulatory_capital_calculation") or "Not performed"),
        },
    ]


def _split_report_sections(report: str | None) -> list[dict[str, str]]:
    if not report:
        return []

    known_headings = {
        "Combined Executive Summary",
        "Market Risk",
        "Market Risk Commentary",
        "Credit Risk",
        "Credit Risk Commentary",
        "Counterparty Risk",
        "Counterparty Risk Commentary",
        "Sensitivity Risk",
        "Sensitivity Risk Commentary",
        "Regulatory Risk",
        "Commentary",
        "Assumptions",
    }
    sections: list[dict[str, str]] = []
    current_title = "Summary"
    current_lines: list[str] = []

    for line in report.splitlines():
        stripped = line.strip()
        if stripped in known_headings:
            if current_lines:
                sections.append(
                    _report_section(current_title, "\n".join(current_lines).strip())
                )
            current_title = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append(_report_section(current_title, "\n".join(current_lines).strip()))

    return [section for section in sections if section["content"]]


def _report_section(title: str, content: str) -> dict[str, str]:
    return {
        "title": title,
        "display_title": _display_report_section_title(title),
        "content": _normalize_ui_labels(content),
    }


def _display_report_section_title(title: str) -> str:
    if title.startswith("Credit Risk") or title.startswith("Counterparty Risk"):
        return "Counterparty Risk"
    if title.startswith("Market Risk"):
        return "Market Risk"
    if title.startswith("Sensitivity Risk"):
        return "Sensitivity Risk"
    if title.startswith("Regulatory Risk"):
        return "Regulatory Risk"
    if "Commentary" in title or "Assumptions" in title:
        return "Commentary / Assumptions"
    return title


def _normalize_ui_labels(text: str) -> str:
    return (
        text.replace("Credit Risk Commentary", "Counterparty Risk Commentary")
        .replace("Credit Risk", "Counterparty Risk")
        .replace("Credit risk", "Counterparty risk")
    )


def _render_readable_markdown(markdown_text: str | None) -> None:
    left, right = st.columns([5, 2])
    with left:
        st.markdown(_normalize_ui_labels(markdown_text or ""))
    with right:
        st.empty()


def _planner_display(requested_planner_mode: str, actual_planner_mode: str) -> str:
    if requested_planner_mode == actual_planner_mode:
        return actual_planner_mode
    return f"{requested_planner_mode} \u2192 {actual_planner_mode}"


def _status_label(status: Any) -> str:
    if status is None:
        return STATUS_LABELS["NOT_RUN"]
    normalized = str(status).upper()
    return STATUS_LABELS.get(normalized, str(status).replace("_", " ").title())


def _display_route(route: Any) -> str:
    if route is None:
        return "None"
    return str(route).replace("_", " ").title()


def _display_execution_mode(mode: Any) -> str:
    return str(mode or "unknown").replace("_", " ").title()


def _display_tool_name(tool_name: Any) -> str:
    return TOOL_LABELS.get(str(tool_name), str(tool_name).replace("_", " ").title())


def _execution_trace_rows(execution_trace: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in execution_trace:
        item = _to_jsonable(entry)
        if not isinstance(item, dict):
            continue
        tool_name = item.get("tool_name")
        if not _is_real_tool_name(tool_name):
            continue
        rows.append(
            {
                "step": item.get("step_number", ""),
                "tool": _display_tool_name(tool_name),
                "status": _status_label(item.get("status")),
                "input summary": item.get("input_summary", ""),
                "output summary": item.get("output_summary", ""),
                "error": item.get("error") or "",
            }
        )
    return rows


def _raw_output_section(result, key: str) -> Any:
    raw_outputs = _to_jsonable(result.raw_outputs)
    if not isinstance(raw_outputs, dict):
        return {}
    return raw_outputs.get(key, {})


def _get_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return "Not available"


def _format_usd(value: Any) -> str:
    try:
        return f"USD {float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not available"


def _clean_tool_names(tool_names) -> list[str]:
    return [
        str(tool_name)
        for tool_name in (tool_names or [])
        if _is_real_tool_name(tool_name)
    ]


def _is_real_tool_name(tool_name: Any) -> bool:
    return tool_name not in (None, "") and str(tool_name).strip().lower() != "none"


def _to_jsonable(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return _to_jsonable(value.__dict__)
    return value


if __name__ == "__main__":
    main()
