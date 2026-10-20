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
