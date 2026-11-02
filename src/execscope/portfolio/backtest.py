"""Daily-bar portfolio backtest with monthly rebalancing, costs and a no-trade band.

Timing (no look-ahead): the decision is taken from data up to the close of rebalance day t and executed at
the close of day t + `lag_days` (default 1). Between rebalances positions drift with prices.
Costs per trade: max(min_fee, notional * cost_bps / 10_000). Whole-share rounding is ignored here (the live
planner does it), so tiny accounts differ slightly from the backtest.
"""
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from execscope.portfolio.strategy import StrategyConfig, compute_target_weights
from execscope.stats.bootstrap import block_bootstrap_diff

TargetFn = Callable[[pd.DataFrame, pd.Timestamp], dict[str, float]]


@dataclass(frozen=True)
class BacktestConfig:
    capital: float = 10_000.0
    lag_days: int = 1
    band: float = 0.01              # do not trade a position whose weight is within 1% of target
    cost_bps: float = 5.0           # commission + spread + slippage, per trade side (ASSUMPTION; measure yours)
    min_fee: float = 1.0            # USD per trade ticket (IBKR-like minimum; ASSUMPTION)
    first_decision: int | None = None   # index of the first decision day (default: strategy min_history)


@dataclass(frozen=True)
class BacktestResult:
    name: str
    equity: pd.Series
    trades: pd.DataFrame
    weights: pd.DataFrame           # target weights at each decision date
    turnover_per_year: float


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Last trading day of each calendar month present in the index."""
    s = pd.Series(index, index=index)
    return list(s.groupby([index.year, index.month]).last())


def run_backtest(name: str, prices: pd.DataFrame, tickers: list[str], cash: str, target_fn: TargetFn,
                 cfg: BacktestConfig = BacktestConfig(), start: int = 0) -> BacktestResult:
    cols = list(dict.fromkeys([*tickers, cash]))
    px = prices[cols]
    rets = px.pct_change().fillna(0.0).to_numpy()
    dates = px.index
    decision_days = {d for d in month_end_dates(dates)}
    pos = np.zeros(len(cols))
    pos[cols.index(cash)] = cfg.capital
    pending: dict[int, dict[str, float]] = {}
    equity, trade_rows, weight_rows = [], [], []
    traded_notional = 0.0
    for i, d in enumerate(dates):
        if i > start:
            pos = pos * (1.0 + rets[i])
        eq = float(pos.sum())
        if i in pending:
            target = pending.pop(i)
            for j, t in enumerate(cols):
                want = target.get(t, 0.0) * eq
                diff = want - pos[j]
                if abs(diff) / eq > cfg.band:
                    fee = max(cfg.min_fee, abs(diff) * cfg.cost_bps / 10_000)
                    pos[j] += diff
                    pos[cols.index(cash)] -= diff + fee
                    traded_notional += abs(diff)
                    trade_rows.append({"date": d, "ticker": t, "notional": diff, "fee": fee})
            eq = float(pos.sum())
        if i >= start and d in decision_days and i + cfg.lag_days < len(dates):
            target = target_fn(px.iloc[: i + 1], d)
            pending[i + cfg.lag_days] = target
            weight_rows.append({"date": d, **{t: target.get(t, 0.0) for t in cols}})
        equity.append(eq)
    eq_series = pd.Series(equity, index=dates).iloc[start:]
    years = max((dates[-1] - dates[start]).days / 365.25, 1e-9)
    trades = pd.DataFrame(trade_rows, columns=["date", "ticker", "notional", "fee"])
    weights = pd.DataFrame(weight_rows).set_index("date") if weight_rows else pd.DataFrame()
    return BacktestResult(name, eq_series, trades, weights, traded_notional / cfg.capital / years)


def strategy_target_fn(cfg: StrategyConfig) -> TargetFn:
    return lambda hist, asof: compute_target_weights(hist, asof, cfg).weights


def constant_target_fn(weights: dict[str, float]) -> TargetFn:
    return lambda hist, asof: dict(weights)


# ----- performance statistics -------------------------------------------------------------------------

def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1.0).min())


def performance(equity: pd.Series, periods: int = 252) -> dict[str, float]:
    r = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1
    vol = float(r.std() * math.sqrt(periods))
    mdd = max_drawdown(equity)
    monthly = equity.resample("ME").last().pct_change().dropna()
    return {
        "cagr": float(cagr), "vol": vol, "sharpe_rf0": float(r.mean() * periods / vol) if vol > 0 else float("nan"),
        "max_drawdown": mdd, "calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
        "worst_month": float(monthly.min()), "best_month": float(monthly.max()),
        "pct_positive_months": float((monthly > 0).mean()), "final_equity": float(equity.iloc[-1]),
    }


def sharpe(returns) -> float:
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(12)) if sd > 0 else 0.0


def compare(prices: pd.DataFrame, cfg: StrategyConfig = StrategyConfig(), bt: BacktestConfig = BacktestConfig()) -> dict:
    """Strategy versus three simple benchmarks on the SAME dates and cost model.

    Benchmarks: SPY buy-and-hold, SPY/IEF 60/40, equal-weight of all risk assets (no trend filter).
    """
    start = bt.first_decision if bt.first_decision is not None else cfg.min_history
    risk = list(cfg.risk_assets)
    runs = {
        "strategy": run_backtest("strategy", prices, risk, cfg.cash, strategy_target_fn(cfg), bt, start),
        "spy": run_backtest("spy", prices, ["SPY"], cfg.cash, constant_target_fn({"SPY": 1.0}), bt, start),
        "60_40": run_backtest("60_40", prices, ["SPY", "IEF"], cfg.cash, constant_target_fn({"SPY": 0.6, "IEF": 0.4}), bt, start),
        "equal_weight": run_backtest("equal_weight", prices, risk, cfg.cash,
                                     constant_target_fn({t: 1 / len(risk) for t in risk}), bt, start),
    }
    out: dict = {"performance": {k: performance(v.equity) for k, v in runs.items()},
                 "turnover_per_year": {k: v.turnover_per_year for k, v in runs.items()},
                 "runs": runs}
    monthly = {k: v.equity.resample("ME").last().pct_change().dropna() for k, v in runs.items()}
    out["sharpe_diff_vs"] = {}
    for k in ("spy", "60_40", "equal_weight"):
        a, b = monthly["strategy"], monthly[k]
        common = a.index.intersection(b.index)
        if len(common) >= 24:
            est, lo, hi = block_bootstrap_diff(a[common].tolist(), b[common].tolist(), sharpe, block=6, n_boot=1000)
            out["sharpe_diff_vs"][k] = {"diff": est, "ci_low": lo, "ci_high": hi, "months": len(common)}
    return out
