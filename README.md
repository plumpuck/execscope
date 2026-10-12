# ExecScope

Execution-quality (TCA) and backtest-fidelity workbench built on top of
[NautilusTrader](https://github.com/nautechsystems/nautilus_trader). Python first.

**Question:** a backtest fills a large buy order at the bar price with zero slippage by default.
How much execution cost does that hide, and how do TWAP-style order slicing and fill/latency
models change the answer?

## Status (learning phase, day 1)
- [x] Environment: venv + `nautilus_trader==1.231.0`
- [x] Ran the official `example_01_load_bars_from_custom_csv` backtest
- [x] First order: buy 1 contract, 1 order / 1 position, fill at bar close, zero commission
- [ ] Large-order experiment (1000 contracts vs. 205 bar volume)
- [ ] M0 parent-order scenario, M1 TWAP, M2 TCA metrics and unit tests

## Layout
- `notes/` plan, learning notes, debug log, interactive notes page (`execscope-notes.html`)
- `examples/` small scripts written while learning (they import files of the official example)

## Credit
Uses NautilusTrader (LGPL-3.0) as a library. Its example code is not copied into this repo.
