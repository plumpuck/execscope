"""Benchmark comparison for one executed parent order.

Each benchmark answers a different question:
  arrival  - what did trading cost versus the price when we started?  (polluted by price drift)
  vwap     - did we beat the market's own average price over the window?  (fair for slow algos)
  close    - how did we do versus the end-of-window price?
"""
from execscope.tca.metrics import average_price, total_quantity
from execscope.tca.shortfall import _sign


def slippage_vs(price: float, benchmark: float, side: str) -> float:
    """Signed cost in bp versus any benchmark: positive = worse than the benchmark."""
    if benchmark <= 0:
        raise ValueError("benchmark must be > 0")
    return _sign(side) * (price - benchmark) / benchmark * 10_000


def participation_rate(filled_qty: float, market_volume: float) -> float:
    """Our share of market volume in the window (0..1+)."""
    if market_volume <= 0:
        raise ValueError("market_volume must be > 0")
    return filled_qty / market_volume


def benchmark_report(
    fills: list[tuple[float, float]], side: str, arrival: float, interval_vwap: float,
    close: float, market_volume: float,
) -> dict[str, float]:
    avg = average_price(fills)
    qty = total_quantity(fills)
    return {
        "avg_fill": avg,
        "vs_arrival_bps": slippage_vs(avg, arrival, side),
        "vs_vwap_bps": slippage_vs(avg, interval_vwap, side),
        "vs_close_bps": slippage_vs(avg, close, side),
        "participation": participation_rate(qty, market_volume),
    }
