# RiskFlow Agent Project History

This document preserves the original Phase 1 project brief for historical context.
It is not the current implementation scope. The current v1 specification is in
`PROJECT_SPEC.md`, and the architecture is documented in `docs/architecture.md`.

## Original Phase 1 Brief

The project started as a portfolio risk analytics backend focused on:

- Loading adjusted close market prices.
- Validating tickers and weights.
- Calculating asset, portfolio, and cumulative returns.
- Computing annualized volatility, historical VaR, Expected Shortfall, maximum drawdown, and correlation.
- Keeping VaR, Expected Shortfall, and max drawdown as positive loss magnitudes.

The initial implementation scope explicitly deferred LLMs, Streamlit, and broader
workflow orchestration. That historical boundary no longer describes the current
RiskFlow Agent v1 implementation.

## Evolution To v1

RiskFlow Agent has since expanded into a controlled LLM-assisted workflow agent:

- Market Risk analytics with portfolio metadata, dollarized risk metrics, and deterministic stress testing.
- Counterparty Risk analytics with exposure profiles, EPE, netting set concentration, and limit utilization.
- Sensitivity Risk aggregation from precomputed upstream Greeks.
- Regulatory Risk readiness checks for SA-CCR and SIMM / RegIM input completeness.
- Planner, tool registry, approved-plan executor, execution trace, methodology retrieval, commentary, and validators.

The current implementation remains deliberately bounded: it does not calculate
SA-CCR EAD, SIMM margin, Monte Carlo PFE, pricing-model Greeks, XVA, or investment advice.
