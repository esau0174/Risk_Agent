from __future__ import annotations

import pandas as pd
import streamlit as st

from src.agent import analyze_portfolio_query_with_llm


DEFAULT_QUERY = (
    "Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. "
    "Focus on downside risk and concentration risk."
)


def main() -> None:
    st.set_page_config(page_title="FinRisk Agent", page_icon="📊", layout="wide")

    st.title("FinRisk Agent")
    st.subheader("LLM-Powered Portfolio Risk Analyst")

    query = st.text_area(
        "Portfolio query",
        value=DEFAULT_QUERY,
        height=130,
    )

    if st.button("Analyze Portfolio", type="primary"):
        if not query.strip():
            st.error("Please enter a portfolio query.")
            return

        try:
            with st.spinner("Analyzing portfolio risk..."):
                result = analyze_portfolio_query_with_llm(query)
        except Exception as exc:
            st.error(f"Unable to analyze portfolio: {exc}")
            return

        _render_results(result)


def _render_results(result: dict) -> None:
    parsed_portfolio = result["parsed_portfolio"]
    risk_report = result["risk_report"]
    risk_metrics = risk_report["risk_metrics"]

    st.divider()

    st.markdown("### Parsed Portfolio")
    portfolio_df = pd.DataFrame(
        {
            "Ticker": parsed_portfolio["tickers"],
            "Weight": [f"{weight:.2%}" for weight in parsed_portfolio["weights"]],
        }
    )
    st.dataframe(portfolio_df, hide_index=True, use_container_width=True)

    st.markdown("### Risk Metrics")
    metrics_df = pd.DataFrame(
        [
            ("Annualized volatility", risk_metrics["annualized_volatility"]),
            ("95% historical VaR", risk_metrics["historical_var"]),
            ("95% Expected Shortfall", risk_metrics["expected_shortfall"]),
            ("Maximum drawdown", risk_metrics["max_drawdown"]),
            ("Latest cumulative return", risk_report["latest_cumulative_return"]),
        ],
        columns=["Metric", "Value"],
    )
    metrics_df["Value"] = metrics_df["Value"].map(lambda value: f"{value:.2%}")
    st.dataframe(metrics_df, hide_index=True, use_container_width=True)

    st.markdown("### Retrieved Methodology Notes")
    methodology_titles = [
        doc["title"] for doc in result.get("retrieved_methodology", [])
    ]
    if methodology_titles:
        for title in methodology_titles:
            st.markdown(f"- {title}")
    else:
        st.caption("No methodology notes were retrieved.")

    st.markdown("### LLM Commentary")
    st.write(result["commentary"])


if __name__ == "__main__":
    main()
