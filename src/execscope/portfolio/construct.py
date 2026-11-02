"""Portfolio construction primitives (pure numpy, no data access).

Weights are fractions of equity; whatever is not invested is cash. Long-only, no leverage.
"""
import numpy as np


def inverse_vol_weights(vols: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Weights proportional to 1/vol over eligible assets, summing to 1 (or all zeros if none)."""
    vols = np.asarray(vols, dtype=float)
    mask = np.asarray(eligible, dtype=bool) & np.isfinite(vols) & (vols > 0)
    w = np.zeros_like(vols)
    if mask.any():
        inv = 1.0 / vols[mask]
        w[mask] = inv / inv.sum()
    return w


def cap_weights(w: np.ndarray, cap: float) -> np.ndarray:
    """Clip each weight at `cap`; the excess is NOT redistributed (it stays in cash).

    Leaving it in cash is deliberate: redistributing would concentrate the portfolio in the other assets.
    """
    if not 0 < cap <= 1:
        raise ValueError("cap must be in (0, 1]")
    return np.minimum(np.asarray(w, dtype=float), cap)


def portfolio_vol(w: np.ndarray, cov: np.ndarray) -> float:
    """Annualised volatility from an annualised covariance matrix."""
    w = np.asarray(w, dtype=float)
    return float(np.sqrt(max(w @ cov @ w, 0.0)))


def vol_target_scale(w: np.ndarray, cov: np.ndarray, target_vol: float, max_gross: float = 1.0) -> np.ndarray:
    """Scale weights so estimated vol is `target_vol`, but never above `max_gross` total (no leverage).

    If the portfolio is already calmer than the target it is NOT levered up: it simply stays fully invested.
    """
    if target_vol <= 0:
        raise ValueError("target_vol must be > 0")
    w = np.asarray(w, dtype=float)
    pv = portfolio_vol(w, cov)
    if pv <= 0 or w.sum() <= 0:
        return w
    scaled = w * (target_vol / pv)
    gross = scaled.sum()
    if gross > max_gross:
        scaled = scaled * (max_gross / gross)
    return scaled
