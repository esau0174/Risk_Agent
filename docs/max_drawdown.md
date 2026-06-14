# Maximum Drawdown

## Purpose
Measure the largest realized peak-to-trough decline in the cumulative portfolio return path.

## Inputs
- Cumulative portfolio return series

## Calculation
Compare each cumulative value with its prior running peak and select the largest decline,
reported as a positive loss magnitude.

## Outputs
- Maximum drawdown as a positive decimal loss magnitude

## Assumptions
- The cumulative path is ordered chronologically and contains valid observations.

## Limitations
- Drawdown is path-dependent and specific to the observed period.
- It does not estimate the probability or timing of a future decline.

## Validation Rules
- Maximum drawdown must be finite and positive for a declining sample.
- Commentary percentages must match the deterministic result within tolerance.

## Related Tools
- `calculate_risk_metrics`
- `validate_report`
