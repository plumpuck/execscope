"""Interval VWAP: the volume-weighted average price of the market over a period."""


def interval_vwap(bars):
    """bars: list of (price, volume) tuples, e.g. [(1.10, 100), (1.20, 300)] -> 1.175.

    Raise ValueError if the list is empty or the total volume is 0.
    """
    total_volume = sum(volume for _, volume in bars)
    if total_volume == 0:
        raise ValueError("total volume is 0")
    return sum(price * volume for price, volume in bars) / total_volume
