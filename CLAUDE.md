# ExecScope - project memory for Claude Code

## What this is
ExecScope = execution-quality TCA (transaction-cost analysis) + backtest-fidelity workbench on NautilusTrader.
Question: when a large parent order is executed (one-shot, TWAP, VWAP, POV, Almgren-Chriss), what does it cost
versus arrival / interval VWAP / close / Perold shortfall, and how far can the backtest fill model be trusted?
It is a resume project for a Quantitative Developer internship (HK/SG; Python, C++, SQL, Linux, Git; trading
systems, research platforms, tools). Target quality: something an institutional execution/quant-dev team
would find methodologically sound, reproducible and readable.

## The user
Chinese speaker, Windows PC, VS Code, new to Python projects and trading. Wants to understand the code, not
just have it. Always: reply in Chinese; open each reply with a 4-line recap (why / done / doing / next);
explain new trading or engineering terms in plain words with a tiny example; give shell commands ONE AT A TIME
for PowerShell (the user pastes them; joined or repeated commands caused many errors).

## Hard rules
1. Never invent results. Numbers that go into the resume or README must come from real-data runs on the
   user's machine, with date range, sample size and 95% intervals. Synthetic data (data/synthetic.py) only
   proves the code works; on pure noise "no difference" is the correct answer.
2. The refsim depth profile is an ASSUMPTION until calibrated on real order-book data; always state it.
3. Binance = crypto. Never describe conclusions as "futures market" conclusions.
4. NautilusTrader is LGPL-3.0: use it as a library through its public API; do not copy its example or source code
   into src/. examples/peek_bar.py is derived from an official example and says so.
5. After each meaningful change: run `python -m pytest`, `ruff check src tests`, `mypy`; then update
   notes/execscope-learning-notes.md and commit + push to github.com/plumpuck/execscope (main).
   Commit trailer: "Co-Authored-By: Claude <noreply@anthropic.com>".

## Layout (details in docs/guide.md)
src/execscope/{tca,algos,models,stats,refsim,data,backtest,experiments,service,explain}; tests/; sql/;
configs/; docs/; notes/. Install: `pip install -e ".[backtest,service,dev]"` (Python >= 3.12).

## Verified facts / pitfalls (keep)
- Nautilus 1.231.0 default bar fill model: market order fills at bar close, slips at most one tick regardless
  of size; bar volume is split into 4 sub-ticks. 100,000 lots of 6E crashed on Money max (notional > ~9.2e9).
- pandas >= 3: BarDataWrangler raises "buffer source array is read-only" on an all-float frame; handled in
  backtest/runner.py::_wrangler_ready.
- With 1-minute bars, any latency below one bar is quantised to "fill on the next bar" (1s = 30s = 60s).
- FillModel(prob_slippage) with a fixed seed draws the same random number for every parent order; the harness
  therefore uses one seed per parent (shared by all algorithms to keep comparisons paired).
- Cost vs arrival price is polluted by drift (slow algos look expensive in uptrends, cheap in downtrends);
  always read it together with cost vs interval VWAP.
- Windows differences: activate with `.\.venv\Scripts\Activate.ps1`; new PowerShell may need
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Not yet verified
Docker image build; Windows test run; real Binance file layouts (written from Binance docs, tested on synthetic
files); any real-data result.
