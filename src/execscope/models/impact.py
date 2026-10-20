"""Square-root market-impact model and its calibration.

    impact_bps = Y * sigma_bps * sqrt(Q / V)

Q = quantity traded, V = market volume over the same horizon (ADV for a daily model),
sigma_bps = volatility over that horizon in bp, Y = a dimensionless constant (empirically ~ 1).
This is the standard "square-root law" used as an a-priori cost benchmark.
"""
import math
from collections.abc import Sequence
from dataclasses import dataclass


def sqrt_impact_bps(qty: float, volume: float, sigma_bps: float, y: float = 1.0) -> float:
    if qty < 0 or sigma_bps < 0 or y < 0:
        raise ValueError("qty, sigma_bps and y must be >= 0")
    if volume <= 0:
        raise ValueError("volume must be > 0")
    return y * sigma_bps * math.sqrt(qty / volume)


@dataclass(frozen=True)
class ImpactFit:
    y: float
    r_squared: float
    n: int


def fit_sqrt_impact(observations: Sequence[tuple[float, float, float, float]]) -> ImpactFit:
    """Least-squares Y (regression through the origin) from (qty, volume, sigma_bps, cost_bps).

    x_i = sigma_i * sqrt(q_i / v_i);  Y = sum(x*cost) / sum(x^2).
    r_squared is the uncentred R^2 for a through-origin fit (1 - SSE / sum(cost^2)).
    """
    if len(observations) < 2:
        raise ValueError("need at least 2 observations")
    xs, ys = [], []
    for q, v, s, c in observations:
        if v <= 0 or q < 0 or s < 0:
            raise ValueError("invalid observation")
        xs.append(s * math.sqrt(q / v))
        ys.append(c)
    sxx = sum(x * x for x in xs)
    if sxx == 0:
        raise ValueError("all regressors are zero; cannot fit")
    y = sum(x * c for x, c in zip(xs, ys, strict=False)) / sxx
    sse = sum((c - y * x) ** 2 for x, c in zip(xs, ys, strict=False))
    syy = sum(c * c for c in ys)
    return ImpactFit(y=y, r_squared=1 - sse / syy if syy > 0 else 0.0, n=len(xs))
