from __future__ import annotations

import json
import os
from collections.abc import Sequence

from dotenv import load_dotenv

from src.data.portfolio import validate_weights
from src.data.portfolio_parser import parse_portfolio_text
from src.market_risk.risk_report import generate_portfolio_risk_report
from src.knowledge.rag import load_methodology_docs, retrieve_relevant_methodology


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_START_DATE = "2023-01-01"
GROWTH_TECH_AI_TICKERS = {"QQQ", "NVDA", "MSFT", "AAPL", "SOXX", "SMH"}
BROAD_EQUITY_TICKERS = {"SPY"}
LONG_DURATION_BOND_TICKERS = {"TLT"}


def analyze_portfolio_query_with_llm(query: str) -> dict:
    """Analyze a natural-language portfolio query with local analytics and LLM commentary."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")

    load_dotenv()
    client = _create_openai_client()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    try:
        parsed_portfolio = parse_portfolio_text(query)
    except ValueError:
        parsed_portfolio = _extract_portfolio_with_llm(client, model, query)

    tickers = parsed_portfolio["tickers"]
    weights = validate_weights(tickers, parsed_portfolio["weights"]).tolist()
    parsed_portfolio = {"tickers": tickers, "weights": weights}

    risk_report = generate_portfolio_risk_report(
        tickers,
        weights,
        start_date=DEFAULT_START_DATE,
    )
    methodology_docs = load_methodology_docs()
    methodology_query = _build_methodology_query(query, risk_report)
    retrieved_methodology = retrieve_relevant_methodology(
        methodology_query,
        methodology_docs,
        top_k=4,
    )
    commentary = _generate_risk_commentary(
        client,
        model,
        query,
        risk_report,
        retrieved_methodology,
    )

    return {
        "original_query": query,
        "parsed_portfolio": parsed_portfolio,
        "risk_report": risk_report,
        "retrieved_methodology": retrieved_methodology,
        "commentary": commentary,
    }


def _create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required to run the LLM risk agent.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "The OpenAI Python SDK is required. Install it with `pip install openai`."
        ) from exc

    return OpenAI(api_key=api_key)


def _extract_portfolio_with_llm(client, model: str, query: str) -> dict:
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Extract portfolio tickers and weights from the user query. "
                    "Return weights as decimals that sum to 1. Do not include any commentary."
                ),
            },
            {"role": "user", "content": query},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "portfolio_extraction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "weights": {
                            "type": "array",
                            "items": {"type": "number"},
                        },
                    },
                    "required": ["tickers", "weights"],
                },
            }
        },
    )

    try:
        extracted = json.loads(response.output_text)
    except (AttributeError, json.JSONDecodeError) as exc:
        raise ValueError("LLM did not return valid portfolio JSON.") from exc

    tickers = [str(ticker).upper() for ticker in extracted.get("tickers", [])]
    weights = _normalize_weights(extracted.get("weights", []))

    if not tickers or not weights:
        raise ValueError("LLM could not extract both tickers and weights from the query.")

    try:
        validated_weights = validate_weights(tickers, weights)
    except ValueError as exc:
        raise ValueError(f"LLM extracted invalid portfolio weights: {exc}") from exc

    return {
        "tickers": tickers,
        "weights": validated_weights.tolist(),
    }


def _generate_risk_commentary(
    client,
    model: str,
    query: str,
    risk_report: dict,
    methodology_docs: list[dict],
    stress_results: list[dict] | None = None,
) -> str:
    facts = _build_commentary_facts(risk_report, methodology_docs, stress_results)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a finance-aware risk analyst. Write concise analyst-style commentary "
                    "using only the supplied calculated facts and portfolio composition notes. "
                    "Do not invent metrics, sector percentages, factor loadings, forecasts, price "
                    "targets, or recommendations. Include downside risk, VaR, Expected Shortfall, "
                    "maximum drawdown, the largest single-name or single-ETF weight, factor/sector-style "
                    "concentration inferred from ticker composition, assumptions and limitations, and "
                    "the exact disclaimer: 'This commentary is for analytical demonstration only and "
                    "does not constitute investment advice.' If supplied composition notes "
                    "mention overlapping growth, technology, AI, semiconductor, broad equity, or "
                    "long-duration bond exposure, discuss those notes explicitly. State that inferred "
                    "factor/sector exposure is based on ticker composition and is not calculated from "
                    "a formal factor model. Use only retrieved methodology notes supplied in the facts. "
                    "Describe historical VaR precisely: based on the historical daily return "
                    "distribution, losses exceeded this threshold in approximately the worst tail "
                    "observations in the lookback window. Do not describe VaR as a forward-looking "
                    "probability of future loss. Describe Expected Shortfall as the average loss "
                    "conditional on losses exceeding the VaR threshold. Avoid vague phrases such as "
                    "'worst-case scenarios'. Present all risk metric and loss decimals as percentages, "
                    "using the supplied display percentages rather than raw decimal values. If stress "
                    "results are supplied, add a dedicated 'Stress Scenario Analysis' section covering "
                    "each scenario name, portfolio loss percentage, stressed portfolio value, and main "
                    "per-ticker contributors. State that the stress test is a deterministic proxy and "
                    "not a full factor model. "
                    "When citing methodology, cite note titles exactly in plain text, for example "
                    "'Methodology reference: Historical VaR'. Do not invent citations or cite external "
                    "sources."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original query:\n{query}\n\n"
                    f"Calculated report facts as JSON:\n{json.dumps(facts, indent=2)}"
                ),
            },
        ],
    )

    try:
        commentary = response.output_text.strip()
    except AttributeError as exc:
        raise ValueError("LLM did not return commentary text.") from exc

    if not commentary:
        raise ValueError("LLM returned empty commentary.")

    return commentary


def generate_risk_commentary(
    query: str,
    risk_report: dict | None,
    methodology_docs: list[dict],
    use_llm: bool = True,
    stress_results: list[dict] | None = None,
    pfe_result: dict | None = None,
) -> str:
    """Generate LLM commentary or a deterministic offline fallback."""
    if pfe_result is not None:
        return _generate_pfe_commentary(
            query,
            pfe_result,
            methodology_docs,
            use_llm,
        )

    if use_llm:
        load_dotenv()
        client = _create_openai_client()
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        return _generate_risk_commentary(
            client,
            model,
            query,
            risk_report,
            methodology_docs,
            stress_results,
        )

    return _build_fallback_commentary(risk_report, methodology_docs, stress_results)


def regenerate_risk_commentary_with_validation_errors(
    risk_report: dict | None,
    original_commentary: str,
    validation_errors: list[str],
    validation_warnings: list[str],
    methodology_docs: list[dict],
    use_llm: bool = True,
    stress_results: list[dict] | None = None,
    pfe_result: dict | None = None,
) -> str:
    """Regenerate commentary once using deterministic validation feedback."""
    if pfe_result is not None:
        return _generate_pfe_commentary(
            "Revise the counterparty exposure commentary using validation feedback.",
            pfe_result,
            methodology_docs,
            use_llm,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            original_commentary=original_commentary,
        )

    if not use_llm:
        return _build_fallback_commentary(
            risk_report,
            methodology_docs,
            stress_results,
        )

    load_dotenv()
    client = _create_openai_client()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    facts = _build_commentary_facts(risk_report, methodology_docs, stress_results)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Revise the supplied portfolio risk commentary so it resolves every "
                    "validation error and warning. Use only the supplied calculated facts and "
                    "retrieved methodology notes. Do not invent metrics or citations, make "
                    "investment recommendations, or claim guaranteed outcomes. Preserve clear "
                    "assumptions and limitations. Present metric and stress loss decimals as percentages. "
                    "If stress results are supplied, preserve a dedicated 'Stress Scenario Analysis' "
                    "section and its deterministic proxy limitation. End with the exact disclaimer: "
                    "'This commentary is "
                    "for analytical demonstration only and does not constitute investment advice.'"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Calculated report facts:\n{json.dumps(facts, indent=2)}\n\n"
                    f"Original commentary:\n{original_commentary}\n\n"
                    f"Validation errors:\n{json.dumps(validation_errors, indent=2)}\n\n"
                    f"Validation warnings:\n{json.dumps(validation_warnings, indent=2)}"
                ),
            },
        ],
    )

    try:
        commentary = response.output_text.strip()
    except AttributeError as exc:
        raise ValueError("LLM did not return regenerated commentary text.") from exc

    if not commentary:
        raise ValueError("LLM returned empty regenerated commentary.")

    return commentary


def _build_commentary_facts(
    risk_report: dict,
    methodology_docs: list[dict] | None = None,
    stress_results: list[dict] | None = None,
) -> dict:
    metadata = risk_report["metadata"]
    tickers = metadata["tickers"]
    weights = metadata["weights"]
    largest_index = max(range(len(weights)), key=weights.__getitem__)
    methodology_docs = methodology_docs or []
    stress_results = stress_results or []
    metrics = risk_report["risk_metrics"]

    return {
        "tickers": tickers,
        "weights": weights,
        "start_date": metadata["start_date"],
        "end_date": metadata["end_date"],
        "confidence_level": metadata["confidence_level"],
        "risk_metrics": metrics,
        "dollar_risk_metrics": risk_report.get("dollar_risk_metrics", {}),
        "risk_metrics_display": {
            name: f"{value:.2%}" for name, value in metrics.items()
        },
        "dollar_risk_metrics_display": {
            name: f"USD {value:,.2f}"
            for name, value in risk_report.get("dollar_risk_metrics", {}).items()
        },
        "latest_cumulative_return": risk_report["latest_cumulative_return"],
        "number_of_observations": risk_report["number_of_observations"],
        "largest_weight_concentration": {
            "ticker": tickers[largest_index],
            "weight": weights[largest_index],
        },
        "composition_notes": _infer_composition_notes(tickers),
        "stress_results": [
            {
                **result,
                "portfolio_loss_display": f"{result['portfolio_loss_pct']:.2%}",
                "dollar_portfolio_loss_display": (
                    f"USD {result['dollar_portfolio_loss']:,.2f}"
                    if result.get("dollar_portfolio_loss") is not None
                    else None
                ),
                "stressed_portfolio_value_usd_display": (
                    f"USD {result['stressed_portfolio_value_usd']:,.2f}"
                    if result.get("stressed_portfolio_value_usd") is not None
                    else None
                ),
                "per_ticker_contribution_display": {
                    ticker: f"{details['portfolio_loss_contribution_pct']:.2%}"
                    for ticker, details in result["per_ticker_contributions"].items()
                },
            }
            for result in stress_results
        ],
        "retrieved_methodology": [
            {
                "title": doc["title"],
                "path": doc["path"],
                "content": doc["content"],
                "score": doc["score"],
            }
            for doc in methodology_docs
        ],
    }


def _build_methodology_query(query: str, risk_report: dict) -> str:
    metrics = risk_report["risk_metrics"]
    metric_terms = " ".join(metrics.keys()).replace("_", " ")
    tickers = " ".join(risk_report["metadata"]["tickers"])
    return (
        f"{query} {metric_terms} concentration risk model limitations not investment advice "
        f"{tickers}"
    )


def _infer_composition_notes(tickers: Sequence[str]) -> list[str]:
    ticker_set = {ticker.upper() for ticker in tickers}
    notes = []
    growth_tech_ai = sorted(ticker_set & GROWTH_TECH_AI_TICKERS)
    broad_equity = sorted(ticker_set & BROAD_EQUITY_TICKERS)
    long_duration_bonds = sorted(ticker_set & LONG_DURATION_BOND_TICKERS)

    if broad_equity and growth_tech_ai:
        notes.append(
            f"{', '.join(broad_equity)} provides broad equity exposure, while "
            f"{', '.join(growth_tech_ai)} add overlapping growth, technology, AI, "
            "or semiconductor-oriented exposure. This is inferred from ticker composition, "
            "not calculated from a formal factor model."
        )
    elif growth_tech_ai:
        notes.append(
            f"{', '.join(growth_tech_ai)} indicate growth, technology, AI, or "
            "semiconductor-oriented exposure inferred from ticker composition, not calculated "
            "from a formal factor model."
        )

    if {"QQQ", "NVDA"}.issubset(ticker_set):
        notes.append(
            "QQQ and NVDA together create meaningful growth, technology, and AI-related "
            "exposure inferred from portfolio composition."
        )

    if long_duration_bonds:
        notes.append(
            f"{', '.join(long_duration_bonds)} may provide diversification versus equities, "
            "but hedge effectiveness depends on the interest-rate and inflation regime."
        )

    if not notes:
        notes.append(
            "No explicit factor or sector concentration was calculated; any exposure comments "
            "should be limited to ticker composition."
        )

    return notes


def _normalize_weights(weights: Sequence[float]) -> list[float]:
    normalized = [float(weight) for weight in weights]
    total = sum(normalized)

    if total > 1.5 and abs(total - 100) <= 1e-6:
        return [weight / 100 for weight in normalized]

    return normalized


def _build_fallback_commentary(
    risk_report: dict,
    methodology_docs: list[dict],
    stress_results: list[dict] | None = None,
) -> str:
    metadata = risk_report["metadata"]
    metrics = risk_report["risk_metrics"]
    dollar_metrics = risk_report.get("dollar_risk_metrics", {})
    tickers = metadata["tickers"]
    weights = metadata["weights"]
    largest_index = max(range(len(weights)), key=weights.__getitem__)
    methodology_titles = [doc["title"] for doc in methodology_docs]

    references = ""
    if methodology_titles:
        references = " Methodology references: " + ", ".join(methodology_titles) + "."

    stress_section = _build_fallback_stress_section(stress_results or [])
    dollar_var_text = (
        f" / USD {dollar_metrics['dollar_historical_var']:,.2f}"
        if dollar_metrics.get("dollar_historical_var") is not None
        else ""
    )
    dollar_es_text = (
        f" / USD {dollar_metrics['dollar_expected_shortfall']:,.2f}"
        if dollar_metrics.get("dollar_expected_shortfall") is not None
        else ""
    )
    dollar_drawdown_text = (
        f" / USD {dollar_metrics['dollar_max_drawdown']:,.2f}"
        if dollar_metrics.get("dollar_max_drawdown") is not None
        else ""
    )
    historical_period = (
        f"from {metadata['start_date']} to {metadata['end_date']}"
        if metadata.get("end_date")
        else f"since {metadata['start_date']}"
    )

    return (
        f"The workflow analyzed {', '.join(tickers)} using historical data "
        f"{historical_period}. Annualized volatility is "
        f"{metrics['annualized_volatility']:.2%}, 95% historical VaR is "
        f"{metrics['historical_var']:.2%}{dollar_var_text}. Based on the historical daily return "
        "distribution, losses exceeded this threshold in approximately the worst 5% "
        "of observations in the lookback window. Expected Shortfall is "
        f"{metrics['expected_shortfall']:.2%}{dollar_es_text}; it estimates the average loss conditional "
        "on losses exceeding the VaR threshold. Maximum drawdown is "
        f"{metrics['max_drawdown']:.2%}{dollar_drawdown_text}. The largest single position is "
        f"{tickers[largest_index]} at {weights[largest_index]:.2%}."
        f"{stress_section}"
        "\n\nAssumptions and "
        "limitations: this fallback commentary is based only on calculated metrics, "
        "historical data, and local methodology retrieval. This commentary is for "
        "analytical demonstration only and does not constitute investment advice."
        f"{references}"
    )


def _build_fallback_stress_section(stress_results: list[dict]) -> str:
    if not stress_results:
        return ""

    scenario_summaries = []
    for result in stress_results:
        contributors = sorted(
            result["per_ticker_contributions"].items(),
            key=lambda item: item[1]["portfolio_loss_contribution_pct"],
            reverse=True,
        )
        contributor_summary = ", ".join(
            f"{ticker} ({details['portfolio_loss_contribution_pct']:.2%})"
            for ticker, details in contributors[:3]
        )
        loss_text = f"{result['portfolio_loss_pct']:.2%}"
        if result.get("dollar_portfolio_loss") is not None:
            loss_text += f" / USD {result['dollar_portfolio_loss']:,.2f}"
        if result.get("stressed_portfolio_value_usd") is not None:
            stressed_value_text = (
                f"USD {result['stressed_portfolio_value_usd']:,.2f}"
            )
        else:
            stressed_value_text = f"{result['stressed_portfolio_value']:.2f}"
        scenario_summaries.append(
            f"{result['scenario_name']}: portfolio loss {loss_text}, "
            f"stressed portfolio value {stressed_value_text}, with the main loss "
            f"contributions from {contributor_summary}."
        )

    return (
        "\n\nStress Scenario Analysis\n"
        + " ".join(scenario_summaries)
        + " This is a deterministic proxy stress test, not a full factor model."
    )


def _generate_pfe_commentary(
    query: str,
    pfe_result: dict,
    methodology_docs: list[dict],
    use_llm: bool,
    validation_errors: list[str] | None = None,
    validation_warnings: list[str] | None = None,
    original_commentary: str | None = None,
) -> str:
    if not use_llm:
        return _build_fallback_pfe_commentary(pfe_result, methodology_docs)

    load_dotenv()
    client = _create_openai_client()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    feedback = {
        "validation_errors": validation_errors or [],
        "validation_warnings": validation_warnings or [],
        "original_commentary": original_commentary,
    }
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a counterparty risk analyst. Use only the supplied deterministic "
                    "PFE and expected exposure metrics. Discuss peak PFE, its time, EPE, maximum "
                    "expected exposure, the largest netting set, and limit utilization when "
                    "configured. Do not introduce XVA, PD, LGD, EAD, credit recommendations, "
                    "or invented metrics. Include assumptions "
                    "and limitations. Include a section titled 'Counterparty Exposure / PFE "
                    "Analysis'. State that the exposure profile is supplied or toy-mode and is "
                    "not generated by a full Monte Carlo pricing engine. Include the exact "
                    "disclaimer: 'This commentary is for analytical "
                    "demonstration only and does not constitute investment advice.' Cite only "
                    "supplied methodology titles."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original query:\n{query}\n\n"
                    f"PFE metrics:\n{json.dumps(pfe_result, indent=2)}\n\n"
                    f"Methodology notes:\n{json.dumps(methodology_docs, indent=2)}\n\n"
                    f"Validation feedback:\n{json.dumps(feedback, indent=2)}"
                ),
            },
        ],
    )
    commentary = response.output_text.strip()
    if not commentary:
        raise ValueError("LLM returned empty PFE commentary.")
    return commentary


def _build_fallback_pfe_commentary(
    pfe_result: dict,
    methodology_docs: list[dict],
) -> str:
    pfe_99_text = ""
    if pfe_result.get("peak_pfe_99") is not None:
        pfe_99_text = (
            f" Peak 99% PFE is USD {pfe_result['peak_pfe_99']:,.2f} at "
            f"{pfe_result['time_of_peak_pfe_99']:.2f} years."
        )
    references = ""
    titles = [doc["title"] for doc in methodology_docs]
    if titles:
        references = " Methodology references: " + ", ".join(titles) + "."
    limit_text = _pfe_limit_text(pfe_result)

    return (
        "Counterparty Exposure / PFE Analysis\n"
        f"Peak 95% PFE is USD {pfe_result['peak_pfe_95']:,.2f} at "
        f"{pfe_result['time_of_peak_pfe_95']:.2f} years."
        f"{pfe_99_text} Average expected exposure (EPE) is USD "
        f"{pfe_result['epe']:,.2f}, while maximum expected exposure is USD "
        f"{pfe_result['max_expected_exposure']:,.2f}. The largest netting set by "
        f"peak PFE is {pfe_result['largest_netting_set_by_peak_pfe']} at "
        f"USD {pfe_result['largest_netting_set_peak_pfe_95']:,.2f}. {limit_text} "
        "Assumptions and "
        "limitations: the exposure profile is supplied or toy-mode and is not generated "
        "by a full Monte Carlo pricing engine. These deterministic summaries do not "
        "include XVA or credit model parameters. This commentary "
        "is for analytical demonstration only and does not constitute investment advice."
        f"{references}"
    )


def _pfe_limit_text(pfe_result: dict) -> str:
    if pfe_result.get("limit_utilization") is None:
        return (
            f"No configured credit limit was supplied for "
            f"{pfe_result['largest_netting_set_by_peak_pfe']}, so limit utilization is "
            "reported with WARNING status."
        )
    return (
        "Limit utilization for the largest netting set is "
        f"{pfe_result['limit_utilization']:.2%} of USD "
        f"{pfe_result['configured_limit']:,.2f}, with limit status "
        f"{pfe_result['limit_status']}."
    )
