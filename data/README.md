# data/

Put market-data CSV files here (they are not committed). The runner expects `;`-separated columns
`timestamp_utc;open;high;low;close;volume`, as in the 9-bar sample from the official NautilusTrader
example `examples/backtest/example_01_load_bars_from_custom_csv/6EH4.XCME_1min_bars.csv`
(copy it from your local Nautilus checkout; it is not redistributed here).

Tests do not need real data: `tests/test_backtest.py` generates deterministic synthetic bars.
Synthetic data is only for checking the code, never for drawing market conclusions.
