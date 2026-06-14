# Historical VaR

## Purpose
Estimate a historical portfolio loss threshold at a selected confidence level.

## Inputs
- Portfolio return series
- Confidence level, such as 95%

## Calculation
Take the lower-tail historical return quantile at `1 - confidence_level` and report its loss
magnitude as a positive number.

## Outputs
- Historical VaR as a positive decimal loss magnitude

## Assumptions
- Historical observations are representative of the selected lookback window.
- Daily observations are treated consistently with the configured return frequency.

## Limitations
- VaR does not measure the average loss beyond its threshold.
- Results depend on the sample period and do not forecast future losses.

## Validation Rules
- Confidence level must be strictly between 0 and 1.
- VaR must be a finite, positive loss magnitude.
- Commentary percentages must match the deterministic result within tolerance.

## Related Tools
- `calculate_risk_metrics`
- `validate_report`
