import math

import pytest
from hypothesis import given, strategies as st

from execscope.models.almgren_chriss import ac_expected_cost_and_variance, ac_holdings, ac_schedule
from execscope.models.impact import fit_sqrt_impact, sqrt_impact_bps


def test_ac_zero_kappa_is_twap():
    assert ac_schedule(900, 9, 0.0) == [100] * 9


def test_ac_risk_averse_front_loads():
    s = ac_schedule(1000, 8, 3.0)
    assert sum(s) == 1000
    assert all(s[i] >= s[i + 1] for i in range(len(s) - 1))   # decreasing
    assert s[0] > 1000 / 8                                       # more than TWAP in the first slice


@given(total=st.integers(0, 10**6), n=st.integers(1, 60), k=st.floats(0, 8))
def test_ac_schedule_sums_and_nonnegative(total, n, k):
    s = ac_schedule(total, n, k)
    assert len(s) == n and sum(s) == total and all(x >= 0 for x in s)


def test_ac_holdings_endpoints():
    x = ac_holdings(1000.0, 10, 2.0)
    assert x[0] == pytest.approx(1000.0) and x[-1] == pytest.approx(0.0, abs=1e-9)


def test_twap_minimises_expected_temporary_cost_but_front_loading_cuts_risk():
    twap = [100] * 10
    fast = ac_schedule(1000, 10, 3.0)
    e_t, v_t = ac_expected_cost_and_variance(twap, sigma=0.5, eta=0.01)
    e_f, v_f = ac_expected_cost_and_variance(fast, sigma=0.5, eta=0.01)
    assert e_t < e_f      # even trading has the lowest impact cost
    assert v_f < v_t      # getting out early has the lowest price risk


def test_ac_cost_hand_calculation():
    # eta=2, tau=1, schedule [3, 1]: E = (2/1)*(9+1) = 20;  holdings after trades: 1, 0 -> Var = 4*1*(1+0) = 4
    e, v = ac_expected_cost_and_variance([3, 1], sigma=2.0, eta=2.0, tau=1.0)
    assert e == pytest.approx(20.0) and v == pytest.approx(4.0)


def test_sqrt_impact_hand_case():
    # quadruple the size -> double the impact
    a = sqrt_impact_bps(100, 10_000, 100.0)
    b = sqrt_impact_bps(400, 10_000, 100.0)
    assert a == pytest.approx(10.0) and b == pytest.approx(20.0)


def test_fit_recovers_known_y():
    obs = [(q, 10_000.0, 80.0, 0.7 * 80.0 * math.sqrt(q / 10_000.0)) for q in (50, 100, 400, 900)]
    fit = fit_sqrt_impact(obs)
    assert fit.y == pytest.approx(0.7) and fit.r_squared == pytest.approx(1.0)


def test_fit_rejects_degenerate_input():
    with pytest.raises(ValueError):
        fit_sqrt_impact([(10, 100, 5, 1)])
    with pytest.raises(ValueError):
        fit_sqrt_impact([(0, 100, 5, 1), (0, 100, 5, 2)])
