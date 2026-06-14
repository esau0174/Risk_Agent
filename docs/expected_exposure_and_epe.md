# Expected Exposure and EPE

## Purpose
Summarize expected positive counterparty exposure over the supplied exposure profile.

## Inputs
- Expected exposure at each time point
- Exposure-profile time grid

## Calculation
Calculate EPE as the arithmetic mean of expected exposure observations and identify the maximum
expected exposure in the profile.

## Outputs
- Average expected exposure / EPE
- Maximum expected exposure

## Assumptions
- Each supplied observation receives equal weight in the prototype average.

## Limitations
- The calculation does not apply time weighting, discounting, or regulatory effective EPE conventions.
- Expected exposure is not PFE or exposure at default.

## Validation Rules
- Expected exposure values must be numeric, finite, and non-negative.
- Commentary EPE must match the deterministic result within tolerance.

## Related Tools
- `load_portfolio_file`
- `calculate_pfe_metrics`
- `validate_report`
