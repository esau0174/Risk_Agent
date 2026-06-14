# Concentration Risk

## Purpose
Identify large individual allocations and overlapping exposures inferred from portfolio tickers.

## Inputs
- Tickers
- Validated portfolio weights
- Ticker composition rules

## Calculation
Select the largest portfolio weight and infer broad equity, growth, technology, AI,
semiconductor, or rate-sensitive overlap from known ticker composition.

## Outputs
- Largest single-name or ETF weight
- Qualitative composition-based concentration observations

## Assumptions
- Ticker mappings provide a useful high-level exposure proxy.

## Limitations
- No holdings decomposition, sector percentages, or formal factor loadings are calculated.
- Inferred exposure can change as an ETF's holdings evolve.

## Validation Rules
- Portfolio weights must sum to 1 within tolerance.
- Commentary must label factor or sector exposure as inferred rather than formally modeled.

## Related Tools
- `parse_portfolio`
- `load_portfolio_file`
- `validate_portfolio`
- `generate_commentary`
