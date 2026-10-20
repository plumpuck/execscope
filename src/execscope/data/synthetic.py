"""Deterministic synthetic 1-minute bars with a daily volume cycle. FOR CODE VALIDATION ONLY.

Never draw market conclusions from this data: its price process is a random walk by construction.
"""
import math
import random

import pandas as pd


def synthetic_minute_bars(
    n_days: int = 10, start: str = "2024-01-02", start_price: float = 40_000.0,
    sigma_per_bar: float = 0.0004, mean_volume: float = 20.0, tick: float = 0.01,
    seed: int = 0, bars_per_day: int = 1440,
) -> pd.DataFrame:
    rng = random.Random(seed)
    t0 = pd.Timestamp(start)
    rows, price = [], start_price
    for d in range(n_days):
        for m in range(bars_per_day):
            phase = 2 * math.pi * m / bars_per_day
            vol_mult = 1.0 + 0.6 * math.sin(phase - math.pi / 2)   # quiet start, busy middle, quiet end
            o = price
            c = round((o * math.exp(rng.gauss(0, sigma_per_bar))) / tick) * tick
            hi = max(o, c) + abs(rng.gauss(0, sigma_per_bar / 2)) * o
            lo = min(o, c) - abs(rng.gauss(0, sigma_per_bar / 2)) * o
            hi, lo = round(hi / tick) * tick, round(lo / tick) * tick
            v = max(0.01, rng.gauss(mean_volume * vol_mult, mean_volume * 0.25))
            rows.append((t0 + pd.Timedelta(days=d, minutes=m), o, max(hi, o, c), min(lo, o, c), c, round(v, 3)))
            price = c
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return df.set_index("timestamp")


def synthetic_trades(bars: pd.DataFrame, trades_per_bar: int = 20, seed: int = 0, tick: float = 0.01) -> pd.DataFrame:
    """A trade tape consistent with the given bars (each bar's trades stay inside its high/low and
    follow open -> high -> low -> close). Layout matches Binance aggTrades. VALIDATION ONLY."""
    rng = random.Random(seed)
    rows = []
    tid = 0
    for ts, b in bars.iterrows():
        path = [b["open"], b["high"], b["low"], b["close"]]
        weights = [rng.random() + 0.1 for _ in range(trades_per_bar)]
        total = sum(weights)
        for k in range(trades_per_bar):
            pos = k / max(1, trades_per_bar - 1) * 3          # 0..3 along the 4-point path
            i = min(int(pos), 2)
            price = path[i] + (path[i + 1] - path[i]) * (pos - i)
            price = min(max(round(price / tick) * tick, b["low"]), b["high"])
            t = ts + pd.Timedelta(milliseconds=int(59_000 * k / trades_per_bar) + rng.randint(0, 500))
            rows.append((tid, price, b["volume"] * weights[k] / total, tid, tid, t, rng.random() < 0.5))
            tid += 1
    df = pd.DataFrame(rows, columns=["agg_trade_id", "price", "quantity", "first_trade_id",
                                     "last_trade_id", "transact_time", "is_buyer_maker"])
    return df.set_index("transact_time").sort_index()
