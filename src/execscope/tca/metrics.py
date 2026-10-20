"""Transaction-cost analysis (TCA) helpers. Pure Python, no NautilusTrader needed.

fills: list of (quantity, price) tuples, e.g. [(52, 1.10780), (9948, 1.10785)]
side:  "BUY" or "SELL"
"""


def total_quantity(fills):
    return sum(qty for qty, _ in fills)


def average_price(fills):
    """Quantity-weighted average fill price."""
    total = total_quantity(fills)
    if total == 0:
        raise ValueError("no fills")
    return sum(qty * price for qty, price in fills) / total


def _sign(side):
    if side == "BUY":
        return 1
    if side == "SELL":
        return -1
    raise ValueError(f"side must be BUY or SELL, got {side!r}")


def slippage_bps(fills, arrival_price, side):
    """Slippage vs arrival price in basis points. Positive = you paid more / received less."""
    return _sign(side) * (average_price(fills) - arrival_price) / arrival_price * 10_000


def cost_usd(fills, arrival_price, side, multiplier):
    """Money lost vs filling everything at the arrival price."""
    return _sign(side) * (average_price(fills) - arrival_price) * total_quantity(fills) * multiplier
