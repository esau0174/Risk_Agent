# FinRisk Agent Project Spec

## Project Name

FinRisk Agent

## Project Goal

Build an LLM-powered financial risk analyst agent that can parse natural-language portfolio risk questions, invoke Python-based risk analytics tools, retrieve methodology notes, and generate analyst-style risk reports with assumptions and limitations.

The project should demonstrate:

- Financial risk analytics
- Python engineering
- LLM tool calling
- Retrieval-Augmented Generation
- Explainable financial reporting
- Guardrails against unsupported investment advice

## Target User

A financial analyst, risk analyst, or portfolio manager who wants to quickly understand the downside risk, concentration risk, and stress exposure of a simple equity/ETF portfolio.

## Phase 1 Goal

Build the non-LLM risk analytics backend.

Phase 1 should accept tickers and weights, download historical market data, compute portfolio returns, and calculate core risk metrics.

Example input:

tickers = ["SPY", "QQQ", "NVDA", "TLT"]
weights = [0.4, 0.3, 0.2, 0.1]
start_date = "2023-01-01"
end_date = None
confidence_level = 0.95

Expected outputs:

- Daily asset returns
- Daily portfolio returns
- Cumulative portfolio return
- Annualized volatility
- Historical VaR
- Expected Shortfall
- Maximum drawdown
- Correlation matrix

## Phase 1 Files

src/
  market_data.py
  portfolio.py
  risk_metrics.py
  stress_testing.py

tests/
  test_portfolio.py
  test_risk_metrics.py

## Module Requirements

### market_data.py

Implement:

download_price_data(tickers, start_date, end_date=None)

Requirements:

- Use yfinance.
- Return adjusted close price data as a pandas DataFrame.
- Columns should be ticker symbols.
- Drop rows where all prices are missing.
- Raise a clear error if no data is returned.
- Support a single ticker and multiple tickers.

### portfolio.py

Implement:

validate_weights(tickers, weights)
calculate_asset_returns(price_data)
calculate_portfolio_returns(asset_returns, weights)
calculate_cumulative_returns(portfolio_returns)

Requirements:

- Number of tickers must equal number of weights.
- Weights must sum to 1 within a small tolerance.
- Weights should be converted to a numpy array.
- Asset returns should use daily percentage returns.
- Portfolio returns should be the weighted sum of asset returns.
- Cumulative return should be calculated as `(1 + returns).cumprod() - 1`.

### risk_metrics.py

Implement:

annualized_volatility(returns, trading_days=252)
historical_var(returns, confidence_level=0.95)
expected_shortfall(returns, confidence_level=0.95)
max_drawdown(cumulative_returns)
correlation_matrix(asset_returns)

Definitions:

- Annualized volatility = daily standard deviation x sqrt(252).
- Historical VaR should return a positive loss number.
- For 95% VaR, use the 5th percentile of returns.
- Expected Shortfall should return the average loss beyond the VaR threshold as a positive number.
- Max drawdown should return positive loss magnitude.

Preferred convention:

- VaR returns positive loss magnitude.
- Expected Shortfall returns positive loss magnitude.
- Max drawdown returns positive loss magnitude.

### stress_testing.py

Implement simple scenario analysis later.

For Phase 1, this can be a placeholder.

Future functions:

apply_shock_to_returns(asset_returns, shocks)
run_historical_stress_scenario(portfolio_returns, scenario_start, scenario_end)

## Testing Requirements

Use pytest.

Tests should cover:

- Weight length mismatch
- Weights not summing to 1
- Correct portfolio return calculation
- Historical VaR sign convention
- Expected Shortfall sign convention
- Max drawdown calculation

## Phase 2 Preview

After Phase 1 works, build an LLM tool-calling layer.

The LLM should:

- Parse natural-language portfolio descriptions.
- Extract tickers and weights.
- Decide which risk tools to call.
- Generate a structured risk report.
- Include assumptions and limitations.

Example user query:

Analyze a portfolio with 40% SPY, 30% QQQ, 20% NVDA, and 10% TLT. Focus on downside risk and concentration risk.

## Phase 3 Preview

Add RAG methodology notes.

Create markdown docs for:

- Historical VaR
- Expected Shortfall
- Stress Testing
- Concentration Risk
- Model Limitations

The agent should retrieve relevant notes and cite them in its explanation.

## Guardrails

The agent should not provide direct buy/sell recommendations.

It can provide:

- Risk analysis
- Exposure analysis
- Historical scenario analysis
- Methodology explanation
- Limitations

It should avoid:

- Promising returns
- Claiming predictions are certain
- Recommending specific trades as personalized financial advice

## Phase 1 Implementation Prompt for Codex

You are working in the repository D:\Code\Risk_Agent.

Read PROJECT_SPEC.md first.

Implement Phase 1 only.

Create clean, tested Python modules:

- src/market_data.py
- src/portfolio.py
- src/risk_metrics.py
- src/stress_testing.py

Also implement pytest tests:

- tests/test_portfolio.py
- tests/test_risk_metrics.py

Do not implement the LLM agent yet.
Do not implement Streamlit yet.
Focus on the risk analytics backend.

Follow the conventions in PROJECT_SPEC.md:

- VaR returns positive loss magnitude.
- Expected Shortfall returns positive loss magnitude.
- Max drawdown returns positive loss magnitude.
- Validate portfolio weights carefully.
- Use clear error messages.

After implementation, run pytest and fix any failing tests.