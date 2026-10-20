# ExecScope

Execution-quality TCA and backtest-fidelity workbench on NautilusTrader.
Question it answers: *when a large parent order is executed (one-shot vs TWAP, later VWAP/POV/IS),
what did it cost versus the arrival price, the interval VWAP and the Perold shortfall — and how
much can we trust the backtest's fill model?*

## Layout
| Folder | What is in it |
|---|---|
| `src/execscope/tca/` | `metrics.py`, `shortfall.py` (Perold IS: delay / execution / opportunity / fees), `benchmarks.py` (arrival, VWAP, close, participation) |
| `src/execscope/algos/` | `twap.py`, `vwap.py`, `schedules.py` (volume-profile VWAP, POV). Pure Python |
| `src/execscope/models/` | `almgren_chriss.py` (optimal trajectory), `impact.py` (square-root law + calibration) |
| `src/execscope/stats/` | seeded bootstrap intervals, paired differences, sign test |
| `src/execscope/refsim/` | order-book reference simulator (depth walking, resilience, permanent impact) |
| `src/execscope/data/` | Binance readers, quality checks, bars preparation, synthetic data (code validation only) |
| `src/execscope/backtest/` | NautilusTrader strategy + runner (one-shot, TWAP, VWAP, POV, Almgren-Chriss) |
| `src/execscope/experiments/` | multi-parent harness, E1-E5, CLI |
| `src/execscope/service/`, `sql/` | SQLite store (PostgreSQL-compatible SQL), FastAPI API, dashboard |
| `src/execscope/explain/` | plain-language report + numeric-grounding verifier |
| `tests/` | unit, property (hypothesis) and Nautilus integration tests |
| `docs/guide.md` | **start here**: what every file does, how to run, how to read results |

## Setup (Windows PowerShell, Python 3.12+)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[backtest,service,dev]"
python -m pytest
```

## Experiments
```
python -W ignore -m execscope.experiments.cli e1 --data synthetic:0     # flow check on synthetic data
python -W ignore -m execscope.experiments.cli e1 --data data/btcusdt_1m.csv
```
See `docs/guide.md` for E1-E5, data download and the dashboard (`uvicorn execscope.service.app:app`).

## Status
Roadmap v2 Tier 1-3 implemented and tested on synthetic data. **Real-data results: not yet produced.**
Untested here: Docker build, Windows run.

## Credit and license
Uses NautilusTrader (LGPL-3.0) as a library through its public API. No Nautilus source is copied
into `src/`.
