"""Execution against observed L2 levels, without extrapolating beyond visible depth.

This is a static liquidity benchmark, not a prediction of actual fills or permanent impact.
Prices need not be equally spaced. BUY consumes asks; SELL consumes bids.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    update_id: int
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]

    @property
    def mid(self) -> float:
        return (self.bids[0][0] + self.asks[0][0]) / 2


def parse_snapshot(payload: dict) -> Snapshot:
    """Reject non-finite, empty, crossed, duplicate or out-of-order books rather than sorting them."""
    sides = []
    for name in ("bids", "asks"):
        levels = []
        for row in payload[name]:
            if len(row) != 2:
                raise ValueError("each level must contain price and quantity")
            price, qty = map(float, row)
            if not (math.isfinite(price) and math.isfinite(qty) and price > 0 and qty > 0):
                raise ValueError("prices and quantities must be positive and finite")
            levels.append((price, qty))
        if not levels:
            raise ValueError("both book sides must be nonempty")
        prices = [p for p, _ in levels]
        if any((a <= b if name == "bids" else a >= b) for a, b in zip(prices, prices[1:], strict=False)):
            raise ValueError("book prices must be strictly ordered")
        sides.append(tuple(levels))
    update_id = payload["lastUpdateId"]
    if type(update_id) is not int or update_id < 0:
        raise ValueError("lastUpdateId must be a nonnegative integer")
    book = Snapshot(update_id, sides[0], sides[1])
    if book.bids[0][0] >= book.asks[0][0]:
        raise ValueError("book is locked or crossed")
    return book


def sweep_snapshot(book: Snapshot, side: str, qty: float) -> dict:
    """Quote a hypothetical market sweep. Partial cost is explicit; full cost stays None if censored."""
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if not math.isfinite(qty) or qty <= 0:
        raise ValueError("qty must be positive and finite")
    levels = book.asks if side == "BUY" else book.bids
    sign = 1 if side == "BUY" else -1
    remaining, filled, notional, used = qty, 0.0, 0.0, 0
    for price, size in levels:
        take = min(remaining, size)
        notional += take * price
        filled += take
        remaining = max(0.0, qty - filled)
        used += 1
        if remaining <= qty * 1e-12:
            remaining = 0.0
            break
    avg = notional / filled
    touch = levels[0][0]
    mid_cost = sign * (avg - book.mid) / book.mid * 10_000
    return {
        "side": side, "qty": qty, "filled_qty": filled, "unfilled_qty": remaining,
        "fill_rate": min(1.0, filled / qty), "levels_used": used,
        "visible_qty": sum(q for _, q in levels), "mid": book.mid,
        "best_price": touch, "average_fill_price": avg,
        "spread_bps": (book.asks[0][0] - book.bids[0][0]) / book.mid * 10_000,
        "filled_cost_vs_mid_bps": mid_cost,
        "filled_walk_vs_touch_bps": sign * (avg - touch) / touch * 10_000,
        "full_order_cost_vs_mid_bps": mid_cost if remaining == 0 else None,
        "depth_exhausted": remaining > 0,
    }
