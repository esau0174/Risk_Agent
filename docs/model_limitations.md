# Model Limitations

## Purpose
Define the interpretation boundaries and guardrails shared by FinRisk analytics.

## Inputs
- Calculated risk or exposure results
- Portfolio or exposure-profile composition
- Configured methodology assumptions

## Calculation
No numerical calculation is performed. This specification supplies disclosure and validation
context for generated commentary.

## Outputs
- Assumption and limitation statements
- Analytical-use and investment-advice disclaimer context

## Assumptions
- Deterministic Python calculations are the source of truth for reported metrics.

## Limitations
- Historical relationships may not persist.
- Prototype stress and exposure profiles are not full production pricing models.
- The project does not provide forecasts or personalized investment advice.

## Validation Rules
- Commentary must include assumptions or limitations.
- Commentary must not invent metrics, guarantee outcomes, or make direct trade recommendations.
- Methodology references must match retrieved local notes.

## Related Tools
- `generate_commentary`
- `regenerate_commentary_with_validation_errors`
- `validate_report`
