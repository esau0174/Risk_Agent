from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.agent import analyze_portfolio_query_with_llm


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Skipping LLM agent demo.")
        return

    query = (
        "Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. "
        "Focus on downside risk and concentration risk."
    )

    result = analyze_portfolio_query_with_llm(query)

    print("Phase 2B LLM Risk Agent Demo")
    print("============================")
    print(f"Original query: {result['original_query']}")
    print()
    print("Parsed portfolio:")
    print(f"Tickers: {result['parsed_portfolio']['tickers']}")
    print(f"Weights: {result['parsed_portfolio']['weights']}")
    print()
    print("Risk metrics:")
    metrics = result["risk_report"]["risk_metrics"]
    print(f"Annualized volatility: {metrics['annualized_volatility']:.2%}")
    print(f"95% historical VaR: {metrics['historical_var']:.2%}")
    print(f"95% Expected Shortfall: {metrics['expected_shortfall']:.2%}")
    print(f"Maximum drawdown: {metrics['max_drawdown']:.2%}")
    print()
    print("LLM commentary:")
    print(result["commentary"])


if __name__ == "__main__":
    main()
