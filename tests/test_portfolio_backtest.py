import numpy as np
import pandas as pd
import pytest

from execscope.portfolio.backtest import (
    BacktestConfig,
    compare,
    constant_target_fn,
    max_drawdown,
    month_end_dates,
    performance,
    run_backtest,
    strategy_target_fn,
)
from execscope.portfolio.strategy import StrategyConfig
from execscope.stats.bootstrap import block_bootstrap_diff
from tests.test_portfolio_core import fake_prices

NO_COST = BacktestConfig(cost_bps=0.0, min_fee=0.0, band=0.0)


def test_month_end_dates_picks_last_trading_day():
    idx = pd.bdate_range("2024-01-29", "2024-03-05")
    got = month_end_dates(idx)
    assert pd.Timestamp("2024-01-31") in got and pd.Timestamp("2024-02-29") in got and pd.Timestamp("2024-03-05") in got


def test_all_cash_grows_with_cash_asset():
    p = fake_prices(300)
    res = run_backtest("cash", p, ["SPY"], "BIL", constant_target_fn({"BIL": 1.0}), NO_COST, start=10)
    assert res.equity.iloc[-1] == pytest.approx(10_000 * p["BIL"].iloc[-1] / p["BIL"].iloc[10], rel=1e-9)


def test_single_asset_buy_and_hold_matches_price_ratio_after_execution_day():
    p = fake_prices(300)
    res = run_backtest("spy", p, ["SPY"], "BIL", constant_target_fn({"SPY": 1.0}), NO_COST, start=10)
    first_trade = res.trades["date"].iloc[0]
    expected = p["SPY"].iloc[-1] / p["SPY"].loc[first_trade]
    held = res.equity.iloc[-1] / res.equity.loc[first_trade]
    assert held == pytest.approx(expected, rel=1e-6)   # monthly rebalances back to 100% SPY change nothing


def test_costs_reduce_final_equity_and_turnover_is_reported():
    p = fake_prices(400)
    fn = constant_target_fn({"SPY": 0.5, "IEF": 0.5})
    free = run_backtest("a", p, ["SPY", "IEF"], "BIL", fn, NO_COST, start=10)
    paid = run_backtest("a", p, ["SPY", "IEF"], "BIL", fn, BacktestConfig(cost_bps=20, min_fee=1, band=0.0), start=10)
    assert paid.equity.iloc[-1] < free.equity.iloc[-1]
    assert paid.turnover_per_year > 0


def test_no_trade_band_suppresses_small_rebalances():
    p = fake_prices(400)
    fn = constant_target_fn({"SPY": 0.5, "IEF": 0.5})
    tight = run_backtest("a", p, ["SPY", "IEF"], "BIL", fn, BacktestConfig(band=0.0), start=10)
    loose = run_backtest("a", p, ["SPY", "IEF"], "BIL", fn, BacktestConfig(band=0.30), start=10)
    assert len(loose.trades) < len(tight.trades)


def test_backtest_has_no_lookahead():
    p = fake_prices(600, seed=3)
    cfg = StrategyConfig()
    a = run_backtest("s", p, list(cfg.risk_assets), cfg.cash, strategy_target_fn(cfg), NO_COST, start=cfg.min_history)
    q = p.copy()
    cut = p.index[450]
    q.loc[q.index > cut] = q.loc[q.index > cut] * 5.0           # change the future only
    b = run_backtest("s", q, list(cfg.risk_assets), cfg.cash, strategy_target_fn(cfg), NO_COST, start=cfg.min_history)
    assert a.equity.loc[:cut].equals(b.equity.loc[:cut])


def test_metrics_hand_cases():
    eq = pd.Series([100, 120, 90, 100.0], index=pd.bdate_range("2024-01-01", periods=4))
    assert max_drawdown(eq) == pytest.approx(-0.25)
    idx = pd.bdate_range("2020-01-01", periods=500)
    flat = pd.Series(100 * 1.0004 ** np.arange(500), index=idx)
    perf = performance(flat)
    assert perf["vol"] == pytest.approx(0.0, abs=1e-9) and perf["max_drawdown"] == 0.0


def test_block_bootstrap_is_seeded_and_brackets_estimate():
    rng = np.random.default_rng(1)
    a = rng.normal(0.01, 0.02, 60).tolist()
    b = rng.normal(0.00, 0.02, 60).tolist()
    mean = lambda x: sum(x) / len(x)  # noqa: E731
    r1 = block_bootstrap_diff(a, b, mean, block=6, n_boot=300, seed=2)
    assert r1 == block_bootstrap_diff(a, b, mean, block=6, n_boot=300, seed=2)
    assert r1[1] <= r1[0] <= r1[2]
    with pytest.raises(ValueError):
        block_bootstrap_diff(a[:5], b[:5], mean)


def test_compare_runs_end_to_end_on_synthetic_prices():
    p = fake_prices(1500, seed=5)
    out = compare(p)
    assert set(out["performance"]) == {"strategy", "spy", "60_40", "equal_weight"}
    assert out["performance"]["strategy"]["max_drawdown"] <= 0
    assert "spy" in out["sharpe_diff_vs"]
    s = out["sharpe_diff_vs"]["spy"]
    assert s["ci_low"] <= s["diff"] <= s["ci_high"]
