"""Multi-asset trend + inverse-volatility strategy with a volatility target.

Rule (decided at the close of day t, using data up to and including t):
  1. An asset is ELIGIBLE if its price is above its 200-day average AND its 126-day return is positive.
  2. Eligible assets get weights proportional to 1 / (60-day volatility), each capped at `max_weight`.
  3. The whole portfolio is scaled DOWN so its estimated volatility does not exceed `target_vol`
     (never levered up). Anything not invested sits in the cash ETF.
Nothing is optimised on past returns: every parameter below is a conventional round number fixed in advance.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from execscope.portfolio.construct import cap_weights, inverse_vol_weights, vol_target_scale

TRADING_DAYS = 252


@dataclass(frozen=True)
class StrategyConfig:
    risk_assets: tuple[str, ...] = ("SPY", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ", "UUP")
    cash: str = "BIL"
    sma_days: int = 200
    mom_days: int = 126
    vol_days: int = 60
    max_weight: float = 0.35
    target_vol: float = 0.08
    min_history: int = 210
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TargetWeights:
    weights: dict[str, float]            # includes the cash ticker; sums to 1
    eligible: dict[str, bool]
    vol_estimate: float                  # annualised, risk assets only
    reasons: dict[str, str]


def compute_target_weights(prices: pd.DataFrame, asof: pd.Timestamp, cfg: StrategyConfig = StrategyConfig()) -> TargetWeights:
    """Target weights using ONLY rows with index <= asof."""
    hist = prices.loc[:asof, list(cfg.risk_assets)]
    if len(hist) < cfg.min_history:
        raise ValueError(f"need at least {cfg.min_history} days of history, have {len(hist)}")
    last = hist.iloc[-1]
    sma = hist.iloc[-cfg.sma_days:].mean()
    mom = hist.iloc[-1] / hist.iloc[-1 - cfg.mom_days] - 1
    rets = hist.pct_change().iloc[-cfg.vol_days:]
    vol = rets.std() * np.sqrt(TRADING_DAYS)

    eligible = (last > sma) & (mom > 0) & last.notna() & vol.notna()
    reasons = {}
    for t in cfg.risk_assets:
        if bool(eligible[t]):
            reasons[t] = f"in: above {cfg.sma_days}d avg, {cfg.mom_days}d return {mom[t]:+.1%}, vol {vol[t]:.1%}"
        else:
            why = []
            if not bool(last[t] > sma[t]):
                why.append(f"below {cfg.sma_days}d avg")
            if not bool(mom[t] > 0):
                why.append(f"{cfg.mom_days}d return {mom[t]:+.1%}")
            reasons[t] = "out: " + ", ".join(why or ["missing data"])

    w = inverse_vol_weights(vol.to_numpy(), eligible.to_numpy())
    w = cap_weights(w, cfg.max_weight)
    cov = rets.cov().to_numpy() * TRADING_DAYS
    cov = np.nan_to_num(cov)
    w = vol_target_scale(w, cov, cfg.target_vol, max_gross=1.0)
    est_vol = float(np.sqrt(max(w @ cov @ w, 0.0)))

    weights = {t: float(x) for t, x in zip(cfg.risk_assets, w, strict=True)}
    weights[cfg.cash] = float(max(0.0, 1.0 - w.sum()))
    return TargetWeights(weights=weights, eligible={t: bool(eligible[t]) for t in cfg.risk_assets},
                         vol_estimate=est_vol, reasons=reasons)
