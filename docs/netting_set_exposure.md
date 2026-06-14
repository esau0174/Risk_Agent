# Netting Set Exposure

## Purpose
Describe and compare exposure concentrations across contractual netting sets.

## Inputs
- Netting set identifiers
- Expected exposure profile
- PFE profile

## Calculation
Sum expected exposure observations by netting set and compare each set's peak PFE 95.

## Outputs
- Total expected exposure by netting set
- Largest netting set by peak PFE 95

## Assumptions
- Rows with the same identifier belong to one valid contractual netting set.

## Limitations
- Summing observations through time is descriptive and is not exposure at default.
- Legal enforceability and collateral netting are not independently assessed.

## Validation Rules
- Netting set identifiers must be non-empty.
- Largest-set results must be derived from the supplied profile without invented aggregation.

## Related Tools
- `load_portfolio_file`
- `calculate_pfe_metrics`
- `generate_commentary`
