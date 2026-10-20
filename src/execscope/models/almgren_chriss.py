"""Almgren-Chriss (2000) optimal execution trajectory and its expected cost / risk.

Holdings x(t) fall from X to 0 over horizon T. With temporary-impact coefficient eta, volatility
sigma and risk aversion lam, the optimal continuous path is

    x(t) = X * sinh(kappa * (T - t)) / sinh(kappa * T),    kappa = sqrt(lam * sigma^2 / eta)

`kappa_T = kappa * T` is the one dimensionless knob used here:
  kappa_T -> 0   : TWAP (risk-neutral, trade evenly)
  kappa_T large  : front-loaded (risk-averse, get out fast to cut price-risk)

Discrete costs follow the paper: E[C] = 0.5*gamma*X^2 + eps*X + (eta_tilde/tau) * sum(n_k^2),
Var[C] = sigma^2 * tau * sum(x_k^2), with eta_tilde = eta - 0.5*gamma*tau.
"""
import math
from collections.abc import Sequence

from execscope.algos.schedules import _largest_remainder


def ac_holdings(total_qty: float, n_slices: int, kappa_t: float) -> list[float]:
    """Continuous-valued holdings x_0..x_n at the n+1 slice boundaries."""
    if n_slices < 1:
        raise ValueError("n_slices must be >= 1")
    if kappa_t < 0:
        raise ValueError("kappa_t must be >= 0")
    if kappa_t < 1e-9:
        return [total_qty * (1 - j / n_slices) for j in range(n_slices + 1)]
    denom = math.sinh(kappa_t)
    return [total_qty * math.sinh(kappa_t * (1 - j / n_slices)) / denom for j in range(n_slices + 1)]


def ac_schedule(total_qty: int, n_slices: int, kappa_t: float) -> list[int]:
    """Integer child sizes (sum == total_qty) following the Almgren-Chriss path."""
    if total_qty < 0:
        raise ValueError("total_qty must be >= 0")
    x = ac_holdings(float(total_qty), n_slices, kappa_t)
    trades = [x[j] - x[j + 1] for j in range(n_slices)]
    if total_qty == 0:
        return [0] * n_slices
    return _largest_remainder(total_qty, trades)


def ac_expected_cost_and_variance(
    schedule: Sequence[float], sigma: float, eta: float, tau: float = 1.0,
    gamma: float = 0.0, epsilon: float = 0.0,
) -> tuple[float, float]:
    """Expected shortfall and its variance for a given integer schedule (paper's discrete form).

    sigma: price volatility per sqrt(unit time); tau: slice length in the same time unit.
    """
    if tau <= 0 or eta <= 0 or sigma < 0:
        raise ValueError("tau and eta must be > 0, sigma >= 0")
    total = float(sum(schedule))
    holdings = []
    left = total
    for n in schedule:
        left -= n
        holdings.append(left)          # x_k after trade k, k = 1..N
    eta_tilde = eta - 0.5 * gamma * tau
    expected = 0.5 * gamma * total**2 + epsilon * total + eta_tilde / tau * sum(n * n for n in schedule)
    variance = sigma**2 * tau * sum(x * x for x in holdings)
    return expected, variance
