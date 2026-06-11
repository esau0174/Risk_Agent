from __future__ import annotations

import json
import os
from collections.abc import Sequence

from dotenv import load_dotenv

from src.portfolio import validate_weights
from src.portfolio_parser import parse_portfolio_text
from src.rag import load_methodology_docs, retrieve_relevant_methodology
from src.risk_report import generate_portfolio_risk_report


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
) -> str:
    facts = _build_commentary_facts(risk_report, methodology_docs)
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
                    "a disclaimer that this is not investment advice. If supplied composition notes "
                    "mention overlapping growth, technology, AI, semiconductor, broad equity, or "
                    "long-duration bond exposure, discuss those notes explicitly. State that inferred "
                    "factor/sector exposure is based on ticker composition and is not calculated from "
                    "a formal factor model. Use only retrieved methodology notes supplied in the facts. "
                    "Describe historical VaR precisely: based on the historical daily return "
                    "distribution, losses exceeded this threshold in approximately the worst tail "
                    "observations in the lookback window. Do not describe VaR as a forward-looking "
                    "probability of future loss. Describe Expected Shortfall as the average loss "
                    "conditional on losses exceeding the VaR threshold. Avoid vague phrases such as "
                    "'worst-case scenarios'. "
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


def _build_commentary_facts(
    risk_report: dict,
    methodology_docs: list[dict] | None = None,
) -> dict:
    metadata = risk_report["metadata"]
    tickers = metadata["tickers"]
    weights = metadata["weights"]
    largest_index = max(range(len(weights)), key=weights.__getitem__)
    methodology_docs = methodology_docs or []

    return {
        "tickers": tickers,
        "weights": weights,
        "start_date": metadata["start_date"],
        "end_date": metadata["end_date"],
        "confidence_level": metadata["confidence_level"],
        "risk_metrics": risk_report["risk_metrics"],
        "latest_cumulative_return": risk_report["latest_cumulative_return"],
        "number_of_observations": risk_report["number_of_observations"],
        "largest_weight_concentration": {
            "ticker": tickers[largest_index],
            "weight": weights[largest_index],
        },
        "composition_notes": _infer_composition_notes(tickers),
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
