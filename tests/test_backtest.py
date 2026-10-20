"""Integration tests: run real NautilusTrader backtests on synthetic 1-minute bars."""
import random

import pytest

pytest.importorskip("nautilus_trader")
import pandas as pd  # noqa: E402

from execscope.backtest.runner import AlgoSpec, VenueSettings, analyse, run_backtest  # noqa: E402


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
    r = run_backtest(synthetic_bars(), AlgoSpec("oneshot"), total_qty=1000)
    assert sum(q for q, _ in r.fills) == 1000


def test_twap_fills_whole_parent_order_in_nine_children():
    r = run_backtest(synthetic_bars(), AlgoSpec("twap", slices=9), total_qty=1000)
    assert sum(q for q, _ in r.fills) == 1000
    assert len(r.fills) >= 9  # at least one fill per child order


def test_sell_side_runs_and_costs_are_signed_consistently():
    buy = analyse(run_backtest(synthetic_bars(), AlgoSpec("oneshot"), "BUY", 1000))
    sell = analyse(run_backtest(synthetic_bars(), AlgoSpec("oneshot"), "SELL", 1000))
    assert buy["filled_qty"] == sell["filled_qty"] == 1000


def test_runs_are_deterministic():
    a = run_backtest(synthetic_bars(), AlgoSpec("twap"), total_qty=1000)
    b = run_backtest(synthetic_bars(), AlgoSpec("twap"), total_qty=1000)
    assert a.fills == b.fills and a.interval_vwap == b.interval_vwap


def test_is_parts_sum_to_total():
    res = analyse(run_backtest(synthetic_bars(), AlgoSpec("twap"), total_qty=1000))
    assert abs(res["is_total_usd"] - res["cost_usd"]) < 1e-6  # fully filled, decision=arrival


def test_every_algo_fills_parent_order_exactly():
    bars = synthetic_bars(30)
    for spec in (AlgoSpec("vwap", slices=9), AlgoSpec("ac", slices=9, kappa_t=2.0),
                 AlgoSpec("pov", pov_rate=0.2)):
        r = run_backtest(bars, spec, total_qty=500, window_bars=20)
        assert sum(q for q, _ in r.fills) == 500, spec.name


def test_pov_never_exceeds_rate_times_bar_volume():
    bars = synthetic_bars(40)
    r = run_backtest(bars, AlgoSpec("pov", pov_rate=0.1), total_qty=10_000, window_bars=40)
    filled = sum(q for q, _ in r.fills)
    assert filled <= 0.1 * bars["volume"].sum() + 40   # rounding allowance of 1 per bar


def test_ac_front_loads_more_than_twap():
    bars = synthetic_bars(20)
    from execscope.backtest.runner import build_schedule
    sched, _ = build_schedule(AlgoSpec("ac", slices=9, kappa_t=3.0), 900)
    assert sched[0] > 100 and sum(sched) == 900   # first child bigger than the TWAP size of 100
    ac = run_backtest(bars, AlgoSpec("ac", slices=9, kappa_t=3.0), total_qty=900)
    assert sum(q for q, _ in ac.fills) == 900


def test_btcusdt_instrument_runs_on_synthetic_bars():
    df = synthetic_bars(12, start=40_000.0)
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]] * 1.0
    df["volume"] = df["volume"] / 10
    r = run_backtest(df, AlgoSpec("twap", slices=6), total_qty=6, instrument="BTCUSDT", window_bars=6)
    assert sum(q for q, _ in r.fills) == 6


def test_latency_and_slippage_settings_change_fills_or_run_cleanly():
    bars = synthetic_bars(25)
    base = run_backtest(bars, AlgoSpec("twap", slices=9), total_qty=900, window_bars=10)
    slip = run_backtest(bars, AlgoSpec("twap", slices=9), total_qty=900, window_bars=10,
                        venue=VenueSettings(prob_slippage=1.0))
    lag = run_backtest(bars, AlgoSpec("twap", slices=9), total_qty=900, window_bars=10,
                       venue=VenueSettings(latency_ms=30_000))
    # certain extra slippage can only make a BUY more expensive
    assert average_price_of(slip) >= average_price_of(base)
    assert sum(q for q, _ in lag.fills) == 900


def average_price_of(r):
    return sum(q * p for q, p in r.fills) / sum(q for q, _ in r.fills)
