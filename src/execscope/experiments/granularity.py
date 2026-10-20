"""E4 - what does using 1-minute bars (instead of the trade tape) do to the benchmarks?

Bar data hides what happened inside each minute. Two measurable consequences:
  * bar VWAP (typical-price proxy) differs from the TRUE VWAP computed from trades
  * the "arrival price" taken as a bar close differs from the last actual trade before the start

For each parent window we report both gaps in bp, plus the high-low range of the first bar (the
price uncertainty a bar-based backtest cannot resolve).
"""
import pandas as pd

from execscope.data.binance import trades_to_bars


def true_vwap(trades: pd.DataFrame) -> float:
    return float((trades["price"] * trades["quantity"]).sum() / trades["quantity"].sum())


def bar_vwap(bars: pd.DataFrame) -> float:
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3
    return float((typical * bars["volume"]).sum() / bars["volume"].sum())


def granularity_bias(trades: pd.DataFrame, starts: list[pd.Timestamp], horizon_minutes: int) -> pd.DataFrame:
    rows = []
    for t0 in starts:
        t1 = t0 + pd.Timedelta(minutes=horizon_minutes)
        window = trades.loc[t0: t1 - pd.Timedelta(microseconds=1)]
        if window.empty:
            continue
        bars = trades_to_bars(window)
        first = bars.iloc[0]
        t_v, b_v = true_vwap(window), bar_vwap(bars)
        before = trades.loc[: t0 - pd.Timedelta(microseconds=1)]
        arrival_tape = float(before["price"].iloc[-1]) if len(before) else float(window["price"].iloc[0])
        rows.append({
            "start": t0,
            "bar_vwap_vs_true_bps": (b_v - t_v) / t_v * 1e4,
            "bar_close_vs_tape_arrival_bps": (float(first["close"]) - arrival_tape) / arrival_tape * 1e4,
            "first_bar_range_bps": (float(first["high"]) - float(first["low"])) / float(first["open"]) * 1e4,
        })
    return pd.DataFrame(rows)
