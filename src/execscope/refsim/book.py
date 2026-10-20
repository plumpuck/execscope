"""Reference execution simulator: a limit order book that a market order WALKS through.

Why it exists: NautilusTrader's default bar-based fill model only ever fills at the bar close plus
at most one tick of slippage, however large the order is. A real order consumes depth level by level
and pays progressively worse prices. This simulator makes that mechanism explicit so the default
model can be benchmarked against it (experiment E3).

Pure Python, no Nautilus. The depth profile is a MODEL (assumption) until it is calibrated from real
level-2 data: size at level k = depth_at_best * (1 + level_growth * k).

Per-bar dynamics (`simulate_schedule`): after each child order the consumed depth refills by the
fraction `resilience` before the next child (1 = fully recovered, 0 = never), and the mid price
moves permanently by `permanent_impact_per_unit` x signed quantity traded.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class BookParams:
    tick: float
    depth_at_best: float          # size available at the best price (units, e.g. contracts or BTC)
    level_growth: float = 1.0     # deeper levels are larger: size_k = depth_at_best * (1 + growth * k)
    n_levels: int = 50
    resilience: float = 1.0       # fraction of consumed depth that refills before the next child order
    permanent_impact_per_unit: float = 0.0   # price units moved per unit traded (signed by side)


def _sign(side: str) -> int:
    if side == "BUY":
        return 1
    if side == "SELL":
        return -1
    raise ValueError("side must be BUY or SELL")


def level_sizes(p: BookParams) -> list[float]:
    return [p.depth_at_best * (1 + p.level_growth * k) for k in range(p.n_levels)]


def walk(
    sizes: list[float], best_price: float, tick: float, side: str, qty: float,
) -> tuple[list[tuple[float, float]], list[float]]:
    """Consume `qty` through the levels. Returns (fills, remaining sizes). A BUY walks UP from the best
    ask, a SELL walks DOWN from the best bid. Quantity beyond the book is left unfilled."""
    if qty < 0:
        raise ValueError("qty must be >= 0")
    s = _sign(side)
    left = qty
    fills, new_sizes = [], list(sizes)
    for k, size in enumerate(sizes):
        if left <= 0:
            break
        take = min(left, size)
        fills.append((take, best_price + s * k * tick))
        new_sizes[k] = size - take
        left -= take
    return fills, new_sizes


def simulate_schedule(
    schedule: list[float], mids: list[float], side: str, params: BookParams,
) -> tuple[list[tuple[float, float]], float]:
    """Execute child sizes `schedule[i]` at bar i against `mids[i]` (the reference price of bar i).

    Returns (all fills, arrival price). Arrival = mids[0]. The best price at bar i is
    mids[i] + permanent shift so far (BUY pushes later prices up, SELL pushes them down).
    """
    if len(schedule) > len(mids):
        raise ValueError("need one mid price per child order")
    s = _sign(side)
    full = level_sizes(params)
    sizes = list(full)
    shift = 0.0
    all_fills: list[tuple[float, float]] = []
    for i, qty in enumerate(schedule):
        if i > 0:   # refill part of what the previous child consumed
            sizes = [cur + params.resilience * (f - cur) for cur, f in zip(sizes, full, strict=False)]
        if qty > 0:
            best = mids[i] + shift
            fills, sizes = walk(sizes, best, params.tick, side, qty)
            all_fills.extend(fills)
            shift += s * params.permanent_impact_per_unit * sum(q for q, _ in fills)
    if any(not isfinite(p) for _, p in all_fills):
        raise ValueError("non-finite price")
    return all_fills, mids[0]
