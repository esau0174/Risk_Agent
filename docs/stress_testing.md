# Stress Testing

## Purpose
Estimate portfolio losses under configured deterministic equity, technology, and rates shocks.

## Inputs
- Tickers and validated weights
- Equity selloff percentage
- Technology selloff percentage
- Rates shock in basis points

## Calculation
Apply broad-equity shocks to SPY and unknown tickers, a technology shock to QQQ, a 1.5 times
technology shock to NVDA, and a 15-year duration proxy to TLT.

## Outputs
- Stressed portfolio value
- Portfolio loss percentage
- Per-ticker loss contributions
- Scenario assumptions

## Assumptions
- Base portfolio value is normalized to 100.
- Shocks are instantaneous and deterministic.

## Limitations
- The prototype excludes correlations, nonlinear pricing, liquidity effects, and a formal factor model.

## Validation Rules
- Scenario inputs must remain within configured bounds.
- Commentary losses, values, and clearly labeled contributions must match results within tolerance.

## Related Tools
- `load_risk_config`
- `run_stress_test`
- `generate_commentary`
- `validate_report`
