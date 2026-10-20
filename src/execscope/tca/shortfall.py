"""Implementation Shortfall (Perold) decomposition for one parent order.

Reference ("paper") portfolio: the whole target quantity is bought at the DECISION price.
Real portfolio: part of it is filled at actual prices, the rest is never executed.

    IS = s * [ (avg_fill - decision) * Q_exec + (end_price - decision) * Q_unexec ] + fees

where s = +1 for BUY and -1 for SELL. It splits into four parts that sum exactly to IS:

    delay        = s * (arrival  - decision) * Q_exec     price drift before the order reached the market
    execution    = s * (avg_fill - arrival)  * Q_exec     cost of trading (impact, spread, slippage)
    opportunity  = s * (end_price - decision) * Q_unexec  cost of the part that was never filled
    fees         = explicit fees (always a cost, passed in already positive)

All amounts in quote currency (USD) = price difference * quantity * multiplier.
"""
from dataclasses import dataclass


def _sign(side: str) -> int:
    if side == "BUY":
        return 1
    if side == "SELL":
        return -1
    raise ValueError(f"side must be BUY or SELL, got {side!r}")


@dataclass(frozen=True)
class ShortfallResult:
    delay: float
    execution: float
    opportunity: float
    fees: float
    total: float
    total_bps: float        # relative to decision-price notional of the TARGET quantity
    executed_qty: float
    unexecuted_qty: float
    avg_fill: float | None  # None when nothing was filled


def implementation_shortfall(
    fills: list[tuple[float, float]],
    side: str,
    target_qty: float,
    decision_price: float,
    arrival_price: float,
    end_price: float,
    multiplier: float = 1.0,
    fees: float = 0.0,
) -> ShortfallResult:
    s = _sign(side)
    if target_qty <= 0:
        raise ValueError("target_qty must be positive")
    if decision_price <= 0 or multiplier <= 0:
        raise ValueError("decision_price and multiplier must be positive")
    if fees < 0:
        raise ValueError("fees must be >= 0 (a cost)")

    q_exec = sum(q for q, _ in fills)
    if q_exec > target_qty + 1e-9:
        raise ValueError("filled more than the target quantity")
    q_unexec = target_qty - q_exec

    if q_exec > 0:
        avg_fill = sum(q * p for q, p in fills) / q_exec
        delay = s * (arrival_price - decision_price) * q_exec * multiplier
        execution = s * (avg_fill - arrival_price) * q_exec * multiplier
    else:
        avg_fill = None
        delay = execution = 0.0
    opportunity = s * (end_price - decision_price) * q_unexec * multiplier

    total = delay + execution + opportunity + fees
    notional = decision_price * target_qty * multiplier
    return ShortfallResult(
        delay=delay,
        execution=execution,
        opportunity=opportunity,
        fees=fees,
        total=total,
        total_bps=total / notional * 10_000,
        executed_qty=q_exec,
        unexecuted_qty=q_unexec,
        avg_fill=avg_fill,
    )


def vwap_slippage_bps(avg_fill: float, interval_vwap: float, side: str) -> float:
    """Cost versus the interval VWAP benchmark, in bp (positive = worse than VWAP)."""
    return _sign(side) * (avg_fill - interval_vwap) / interval_vwap * 10_000
