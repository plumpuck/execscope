# ExecScope

Execution-quality TCA and backtest-fidelity workbench on NautilusTrader.
Question it answers: *when a large parent order is executed (one-shot vs TWAP, later VWAP/POV/IS),
what did it cost versus the arrival price, the interval VWAP and the Perold shortfall — and how
much can we trust the backtest's fill model?*

## Layout
| Folder | What is in it |
|---|---|
| `src/execscope/tca/` | `metrics.py` (avg price, slippage bp, USD cost), `shortfall.py` (Perold Implementation Shortfall split into delay / execution / opportunity / fees; VWAP slippage) |
| `src/execscope/algos/` | `twap.py` (slice schedule), `vwap.py` (interval VWAP). Pure Python, no Nautilus needed |
| `src/execscope/backtest/` | `strategies.py` (one-shot and TWAP execution strategy), `runner.py` (run a backtest and compute costs; CLI) |
| `tests/` | unit tests + Nautilus integration tests on synthetic bars |
| `data/` | where to put the CSV (see `data/README.md`) |
| `examples/` | small learning scripts derived from the official Nautilus example (LGPL-3.0) |
| `docs/`, `notes/` | architecture diagrams, roadmap v2, learning notes, resume draft |

## Setup (Windows PowerShell, Python 3.12+)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[backtest,dev]"
python -m pytest
```
Expected: `25 passed` (a Pandas deprecation warning from Nautilus is harmless).

## Run the comparison
```
python -W ignore -m execscope.backtest.runner --data path\to\6EH4.XCME_1min_bars.csv
```
Prints one-shot and TWAP results for a 10,000-lot BUY.

## Status
Tier 1 of `docs/roadmap-v2.md`. Done: TCA metrics, Perold IS, TWAP/VWAP helpers, Nautilus
one-shot/TWAP runs, tests. Next: more benchmarks, VWAP/POV strategies, repeated experiments with
confidence intervals, config files, CI.

## Credit and license
Uses NautilusTrader (LGPL-3.0) as a library through its public API. No Nautilus source is copied
into `src/`.
