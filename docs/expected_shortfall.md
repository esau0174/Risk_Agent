# Expected Shortfall

## Purpose
Estimate the average historical loss conditional on losses exceeding the VaR threshold.

## Inputs
- Portfolio return series
- Confidence level
- Historical VaR tail threshold

## Calculation
Average returns in the lower tail at or below the historical VaR quantile, then report the
result as a positive loss magnitude.

## Outputs
- Expected Shortfall (ES) as a positive decimal loss magnitude

## Assumptions
- The historical tail contains enough observations to summarize severe losses.
- Returns use the same frequency and lookback window as VaR.

## Limitations
- ES remains sample-dependent and is not a forward-looking worst-case estimate.
- Sparse tails can make the estimate unstable.

## Validation Rules
- ES must be finite and positive.
- ES must be greater than or equal to historical VaR.
- Commentary percentages must match the deterministic result within tolerance.

## Related Tools
- `calculate_risk_metrics`
- `validate_report`
