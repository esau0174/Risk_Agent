from __future__ import annotations

import json
import os
from collections.abc import Sequence

from dotenv import load_dotenv

from src.portfolio import validate_weights
from src.portfolio_parser import parse_portfolio_text
from src.risk_report import generate_portfolio_risk_report


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_START_DATE = "2023-01-01"


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
    commentary = _generate_risk_commentary(client, model, query, risk_report)

    return {
        "original_query": query,
        "parsed_portfolio": parsed_portfolio,
        "risk_report": risk_report,
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


def _generate_risk_commentary(client, model: str, query: str, risk_report: dict) -> str:
    facts = _build_commentary_facts(risk_report)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a risk analyst. Write concise analyst-style commentary using only "
                    "the supplied calculated facts. Do not invent metrics, forecasts, targets, "
                    "or recommendations. Include downside risk, VaR, Expected Shortfall, maximum "
                    "drawdown, largest-weight concentration, assumptions and limitations, and a "
                    "disclaimer that this is not investment advice."
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


def _build_commentary_facts(risk_report: dict) -> dict:
    metadata = risk_report["metadata"]
    tickers = metadata["tickers"]
    weights = metadata["weights"]
    largest_index = max(range(len(weights)), key=weights.__getitem__)

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
    }


def _normalize_weights(weights: Sequence[float]) -> list[float]:
    normalized = [float(weight) for weight in weights]
    total = sum(normalized)

    if total > 1.5 and abs(total - 100) <= 1e-6:
        return [weight / 100 for weight in normalized]

    return normalized
