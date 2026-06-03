# Historical VaR

Historical Value at Risk (VaR) estimates a loss threshold from observed return history.
For a 95% confidence level, the 5th percentile of historical portfolio returns is used.
In this project, VaR is reported as a positive loss magnitude.

VaR is easy to explain and does not require a parametric return distribution assumption.
However, it depends on the chosen lookback window and does not describe the average size of
losses beyond the VaR threshold.
