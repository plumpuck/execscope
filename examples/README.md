# examples/

Small scripts written while learning NautilusTrader. They are written against the official
example `examples/backtest/example_01_load_bars_from_custom_csv` (develop_v1 branch,
https://github.com/nautechsystems/nautilus_trader) and must be run inside that folder, next to
its `strategy.py` and CSV file.

**Source and license:** NautilusTrader is licensed under LGPL-3.0. These scripts use it as a library
through its public API and follow the structure of its example, so treat them as derived from it.
The official example files (`run_example.py`, `strategy.py`, the CSV) are **not** copied here.

ExecScope's own code, which does not depend on NautilusTrader, lives in `src/`
(`tca.py`, `twap.py`, `vwap.py` and their tests).
