"""Pure-Python child-order sizing rules (no NautilusTrader needed).

All schedules return integer contract counts. Rounding uses the largest-remainder method so the
children always sum to exactly the parent quantity.
"""
from collections.abc import Sequence


def _largest_remainder(total: int, shares: Sequence[float]) -> list[int]:
    """Split `total` into integers proportional to `shares` (non-negative, sum > 0)."""
    s = sum(shares)
    raw = [total * w / s for w in shares]
    base = [int(x) for x in raw]
    short = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - base[i], -i), reverse=True)
    for i in order[:short]:
        base[i] += 1
    return base


def volume_profile_schedule(total_qty: int, weights: Sequence[float]) -> list[int]:
    """VWAP-style schedule: child sizes proportional to an expected volume profile."""
    if total_qty < 0:
        raise ValueError("total_qty must be >= 0")
    if len(weights) == 0:
        raise ValueError("weights must not be empty")
    if any(w < 0 for w in weights):
        raise ValueError("weights must be >= 0")
    if sum(weights) <= 0:
        raise ValueError("weights must not all be zero")
    return _largest_remainder(total_qty, weights)


def build_volume_profile(volume_by_day: Sequence[Sequence[float]]) -> list[float]:
    """Average intraday volume profile from past days (rows = days, columns = time slots).

    Each day is normalised to sum to 1 first, so one very busy day does not dominate.
    Use only days BEFORE the day you trade, otherwise the backtest looks into the future.
    """
    if not volume_by_day:
        raise ValueError("need at least one day of volumes")
    n = len(volume_by_day[0])
    if any(len(day) != n for day in volume_by_day):
        raise ValueError("all days must have the same number of slots")
    profile = [0.0] * n
    used = 0
    for day in volume_by_day:
        total = sum(day)
        if total <= 0:
            continue
        used += 1
        for i, v in enumerate(day):
            profile[i] += v / total
    if used == 0:
        raise ValueError("all days have zero volume")
    return [p / used for p in profile]


def pov_child_qty(remaining: int, reference_volume: float, rate: float) -> int:
    """Participation-of-volume child size: `rate` x the market volume seen so far (no look-ahead)."""
    if not 0 < rate <= 1:
        raise ValueError("rate must be in (0, 1]")
    if remaining < 0 or reference_volume < 0:
        raise ValueError("remaining and reference_volume must be >= 0")
    return min(remaining, int(round(rate * reference_volume)))
