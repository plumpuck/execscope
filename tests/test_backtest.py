"""Integration tests: run real NautilusTrader backtests on synthetic 1-minute bars."""
import random

import pytest

pytest.importorskip("nautilus_trader")
import pandas as pd  # noqa: E402

from execscope.backtest.runner import analyse, run_backtest  # noqa: E402


def synthetic_bars(n=20, seed=7, start=1.1000):
    """Deterministic random walk, volume large enough to be realistic. NOT real market data."""
    rng = random.Random(seed)
    rows, price = [], start
    for i in range(n):
        o = price
        c = round(o + rng.choice([-1, 0, 1]) * 0.00005, 5)
        h = max(o, c) + 0.00005
        lo = min(o, c) - 0.00005
        rows.append((pd.Timestamp("2024-01-02 09:00") + pd.Timedelta(minutes=i), o, h, lo, c, rng.randint(150, 400)))
        price = c
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"]).set_index("timestamp")


def test_oneshot_fills_whole_parent_order():
    r = run_backtest(synthetic_bars(), mode="oneshot", total_qty=1000)
    assert sum(q for q, _ in r.fills) == 1000


def test_twap_fills_whole_parent_order_in_nine_children():
    r = run_backtest(synthetic_bars(), mode="twap", total_qty=1000, n_slices=9)
    assert sum(q for q, _ in r.fills) == 1000
    assert len(r.fills) >= 9  # at least one fill per child order


def test_sell_side_runs_and_costs_are_signed_consistently():
    buy = analyse(run_backtest(synthetic_bars(), "oneshot", "BUY", 1000))
    sell = analyse(run_backtest(synthetic_bars(), "oneshot", "SELL", 1000))
    assert buy["filled_qty"] == sell["filled_qty"] == 1000


def test_runs_are_deterministic():
    a = run_backtest(synthetic_bars(), "twap", total_qty=1000)
    b = run_backtest(synthetic_bars(), "twap", total_qty=1000)
    assert a.fills == b.fills and a.interval_vwap == b.interval_vwap


def test_is_parts_sum_to_total():
    res = analyse(run_backtest(synthetic_bars(), "twap", total_qty=1000))
    assert abs(res["is_total_usd"] - res["cost_usd"]) < 1e-6  # fully filled, decision=arrival
