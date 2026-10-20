"""Small, dependency-light statistics for comparing execution costs.

Always seeded: the same inputs and seed give the same interval.
"""
import math
import random
from collections.abc import Callable, Sequence


def _mean(v: Sequence[float]) -> float:
    return sum(v) / len(v)


def bootstrap_ci(
    values: Sequence[float], stat: Callable[[Sequence[float]], float] = _mean,
    n_boot: int = 5000, alpha: float = 0.05, seed: int = 0,
) -> tuple[float, float, float]:
    """(estimate, low, high): percentile bootstrap interval of `stat`."""
    if len(values) < 2:
        raise ValueError("need at least 2 values")
    rng = random.Random(seed)
    n = len(values)
    stats = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    lo = stats[int((alpha / 2) * n_boot)]
    hi = stats[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return stat(values), lo, hi


def paired_diff_ci(
    a: Sequence[float], b: Sequence[float], n_boot: int = 5000, alpha: float = 0.05, seed: int = 0,
) -> tuple[float, float, float]:
    """Bootstrap interval of mean(a - b) for paired samples (same parent orders, two algorithms)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    return bootstrap_ci([x - y for x, y in zip(a, b)], n_boot=n_boot, alpha=alpha, seed=seed)


def sign_test_p(diffs: Sequence[float]) -> float:
    """Two-sided exact sign test p-value (ties dropped): is one algorithm better more often than chance?"""
    nz = [d for d in diffs if d != 0]
    n = len(nz)
    if n == 0:
        return 1.0
    k = sum(1 for d in nz if d > 0)
    k = min(k, n - k)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * p)
