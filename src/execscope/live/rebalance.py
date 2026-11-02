"""Turn target weights into whole-share orders, check risk, and (optionally) send them.

Default is a DRY RUN: nothing is sent unless `execute=True` AND the confirm callback says yes.
"""
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from execscope.live.broker import Broker, Order, OrderResult
from execscope.live.risk import DrawdownGuard, RiskError, RiskLimits, check_plan
from execscope.portfolio.strategy import StrategyConfig, compute_target_weights


@dataclass(frozen=True)
class PlanConfig:
    band: float = 0.02               # skip a position whose weight is within 2% of target
    min_trade_value: float = 100.0   # skip trades smaller than this (USD) - fees would eat them
    limit_slippage: float = 0.002    # marketable limit 0.2% through the reference price
    cash_buffer: float = 0.01        # keep 1% un-invested


def plan_orders(equity: float, positions: dict[str, int], prices: dict[str, float], target: dict[str, float],
                cash_symbol: str, cfg: PlanConfig = PlanConfig()) -> list[Order]:
    """Whole-share orders that move `positions` towards `target` weights. Never shorts; sells come first.

    Risk assets are rounded DOWN to whole shares; the cash ETF absorbs the remainder (also in whole shares).
    """
    investable = equity * (1 - cfg.cash_buffer)
    want: dict[str, int] = {}
    for sym, w in target.items():
        px = prices.get(sym)
        if not px or px <= 0:
            continue
        want[sym] = 0 if sym == cash_symbol else math.floor(w * investable / px)
    spent = sum(q * prices[s] for s, q in want.items())
    if cash_symbol in prices:
        want[cash_symbol] = max(0, math.floor((investable - spent) / prices[cash_symbol]))
    orders: list[Order] = []
    for sym in sorted(set(want) | set(positions)):
        px = prices.get(sym)
        if not px:
            continue
        have, goal = positions.get(sym, 0), want.get(sym, 0)
        diff = goal - have
        value = abs(diff) * px
        if diff == 0 or value < cfg.min_trade_value:
            continue
        if abs(diff * px) / equity < cfg.band and goal != 0:
            continue
        side = "BUY" if diff > 0 else "SELL"
        limit = px * (1 + cfg.limit_slippage) if side == "BUY" else px * (1 - cfg.limit_slippage)
        orders.append(Order(sym, side, abs(diff), round(limit, 2)))
    return sorted(orders, key=lambda o: (o.side != "SELL", o.symbol))


def in_rebalance_window(today: datetime, last_rebalance_month: str | None) -> bool:
    """True in the last 4 calendar days of a month if this month has not been rebalanced yet."""
    month_key = today.strftime("%Y-%m")
    if last_rebalance_month == month_key:
        return False
    next_month = (today.replace(day=28) + pd.Timedelta(days=4)).replace(day=1)
    days_left = (next_month - pd.Timestamp(today.date())).days
    return days_left <= 4


@dataclass(frozen=True)
class RebalanceReport:
    executed: bool
    halted: bool
    equity: float
    target: dict[str, float]
    orders: list[Order]
    results: list[OrderResult]
    notes: list[str]


def run_rebalance(broker: Broker, price_history: pd.DataFrame, cfg: StrategyConfig = StrategyConfig(),
                  plan_cfg: PlanConfig = PlanConfig(), limits: RiskLimits = RiskLimits(),
                  state_dir: str = "live_state", execute: bool = False, confirm=lambda text: False,
                  today: datetime | None = None, force: bool = False, max_data_age_days: int = 5) -> RebalanceReport:
    today = today or datetime.now()
    sd = Path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    state_file = sd / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    notes: list[str] = []

    if execute and not force and not in_rebalance_window(today, state.get("last_rebalance_month")):
        raise RiskError("not in the month-end rebalance window (or already done this month); use force=True to override")
    age = (pd.Timestamp(today.date()) - price_history.index[-1]).days
    if age > max_data_age_days:
        raise RiskError(f"latest price in the history is {age} days old; refresh the price file first")

    symbols = sorted({*cfg.risk_assets, cfg.cash, *broker.positions()})
    prices = broker.prices(symbols)
    positions = broker.positions()
    equity = broker.equity(prices)
    guard = DrawdownGuard(str(sd / "drawdown.json"), limits.max_drawdown_halt)
    halted = guard.update(equity)

    if halted:
        target = {cfg.cash: 1.0}
        notes.append(f"HALTED: drawdown limit {limits.max_drawdown_halt:.0%} was hit; moving to cash. "
                     "Trading stays halted until you reset the guard by hand.")
    else:
        tw = compute_target_weights(price_history, price_history.index[-1], cfg)
        target = tw.weights
        notes += [f"{t}: {r}" for t, r in tw.reasons.items()]

    orders = plan_orders(equity, positions, prices, target, cfg.cash, plan_cfg)
    problems = check_plan(orders, equity, positions, prices, broker.cash(), limits)
    if problems:
        raise RiskError("risk check failed: " + "; ".join(problems))

    results: list[OrderResult] = []
    executed = False
    if execute and orders:
        text = "\n".join(f"{o.side} {o.qty} {o.symbol} limit {o.limit_price}" for o in orders)
        if confirm(text):
            for o in orders:
                results.append(broker.submit(o))
            executed = True
            state["last_rebalance_month"] = today.strftime("%Y-%m")
            state_file.write_text(json.dumps(state))
            _audit(sd / "orders.csv", today, broker.name, results)
        else:
            notes.append("not confirmed; nothing was sent")
    return RebalanceReport(executed, halted, equity, target, orders, results, notes)


def _audit(path: Path, ts: datetime, broker: str, results: list[OrderResult]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "broker", "symbol", "side", "requested", "filled", "avg_price", "status", "fee"])
        for r in results:
            w.writerow([ts.isoformat(timespec="seconds"), broker, r.symbol, r.side, r.requested, r.filled,
                        r.avg_price, r.status, r.fee])
