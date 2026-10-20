"""E3 - how much does NautilusTrader's default fill model understate the cost of large orders?

For each parent order the SAME one-shot trade is priced three ways, all measured in bp versus the
arrival price (the first bar's close):
  1. nautilus   : the engine's default bar fill model
  2. refsim     : walking a depth profile (reference simulator, depth = fraction of bar volume)
  3. sqrt_model : the square-root impact law with Y = 1 (an a-priori benchmark)
The "understatement" is (reference - nautilus), by order size.
"""
import math
import statistics
from dataclasses import dataclass

import pandas as pd

from execscope.backtest.runner import AlgoSpec, VenueSettings, analyse, run_backtest
from execscope.models.impact import sqrt_impact_bps
from execscope.refsim.book import BookParams, simulate_schedule
from execscope.stats.bootstrap import bootstrap_ci
from execscope.tca.benchmarks import slippage_vs
from execscope.tca.metrics import average_price


@dataclass(frozen=True)
class FidelityConfig:
    instrument: str = "BTCUSDT"
    level_spacing: float = 0.5     # price step between depth levels (an ASSUMPTION until calibrated on L2 data)
    sizes: tuple[int, ...] = (1, 5, 20, 60)
    depth_fraction: float = 0.25   # depth at best = depth_fraction x that bar's volume (Nautilus splits a bar into 4 ticks)
    level_growth: float = 1.0
    n_boot: int = 1000
    seed: int = 0


def window_sigma_bps(window: pd.DataFrame) -> float:
    """Volatility over the whole window in bp: per-bar std of log returns x sqrt(bars)."""
    r = (window["close"] / window["close"].shift(1)).dropna().map(math.log)
    return statistics.pstdev(r) * math.sqrt(len(window)) * 10_000 if len(r) > 1 else 0.0


def run_fidelity(df: pd.DataFrame, starts: list[int], horizon: int, cfg: FidelityConfig, side: str = "BUY") -> pd.DataFrame:
    rows = []
    for p, s in enumerate(starts):
        w = df.iloc[s: s + horizon]
        first_vol = float(w["volume"].iloc[0])
        mids = [float(c) for c in w["close"]]
        sigma = window_sigma_bps(w)
        for q in cfg.sizes:
            r = run_backtest(w, AlgoSpec("oneshot"), side, q, cfg.instrument, VenueSettings(), window_bars=horizon)
            nautilus = analyse(r)["vs_arrival_bps"]
            params = BookParams(tick=cfg.level_spacing, depth_at_best=cfg.depth_fraction * first_vol,
                                level_growth=cfg.level_growth)
            fills, arrival = simulate_schedule([q], mids, side, params)
            ref = slippage_vs(average_price(fills), arrival, side) if fills else float("nan")
            rows.append({
                "parent": p, "qty": q, "nautilus_bps": nautilus, "refsim_bps": ref,
                "sqrt_bps": sqrt_impact_bps(q, float(w["volume"].sum()), sigma),
            })
    return pd.DataFrame(rows)


def summarise_fidelity(t: pd.DataFrame, cfg: FidelityConfig) -> dict:
    out: dict = {}
    for q, g in t.groupby("qty"):
        entry = {}
        for col in ("nautilus_bps", "refsim_bps", "sqrt_bps"):
            vals = g[col].dropna().tolist()
            est, lo, hi = bootstrap_ci(vals, n_boot=cfg.n_boot, seed=cfg.seed)
            entry[col] = {"mean": est, "ci_low": lo, "ci_high": hi}
        gap = (g["refsim_bps"] - g["nautilus_bps"]).dropna().tolist()
        est, lo, hi = bootstrap_ci(gap, n_boot=cfg.n_boot, seed=cfg.seed)
        entry["understatement_vs_refsim_bps"] = {"mean": est, "ci_low": lo, "ci_high": hi}
        out[int(q)] = entry
    return out
