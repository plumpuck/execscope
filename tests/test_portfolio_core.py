import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from execscope.portfolio.construct import cap_weights, inverse_vol_weights, portfolio_vol, vol_target_scale
from execscope.portfolio.data import check_prices
from execscope.portfolio.strategy import StrategyConfig, compute_target_weights

TICKERS = ("SPY", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ", "UUP", "BIL")


def fake_prices(n=400, seed=0, drift=None, vol=0.01):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    cols = {}
    for t in TICKERS:
        mu = (drift or {}).get(t, 0.0003)
        cols[t] = 100 * np.exp(np.cumsum(rng.normal(mu, vol if t != "BIL" else 0.0001, n)))
    return pd.DataFrame(cols, index=idx)


def test_inverse_vol_hand_case():
    w = inverse_vol_weights(np.array([0.1, 0.2, 0.4]), np.array([True, True, True]))
    assert w == pytest.approx(np.array([4, 2, 1]) / 7)


def test_inverse_vol_ignores_ineligible_and_bad_vols():
    w = inverse_vol_weights(np.array([0.1, 0.2, np.nan, 0.0]), np.array([True, False, True, True]))
    assert w == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert inverse_vol_weights(np.array([0.1]), np.array([False])).sum() == 0


@settings(max_examples=60, deadline=None)
@given(st.lists(st.floats(0.01, 1.0), min_size=2, max_size=9), st.floats(0.05, 1.0))
def test_cap_never_exceeded_and_never_adds_weight(vols, cap):
    w = inverse_vol_weights(np.array(vols), np.ones(len(vols), bool))
    c = cap_weights(w, cap)
    assert (c <= cap + 1e-12).all() and c.sum() <= w.sum() + 1e-12


def test_vol_target_scales_down_but_never_levers_up():
    cov = np.diag([0.04, 0.04])               # each asset 20% vol
    w = np.array([0.5, 0.5])
    scaled = vol_target_scale(w, cov, 0.05)
    assert portfolio_vol(scaled, cov) == pytest.approx(0.05)
    calm = vol_target_scale(w, cov, 0.50)     # target far above actual -> stays fully invested, no leverage
    assert calm.sum() == pytest.approx(1.0)


def test_target_weights_sum_to_one_and_long_only():
    tw = compute_target_weights(fake_prices(), pd.Timestamp("2021-06-01"))
    assert sum(tw.weights.values()) == pytest.approx(1.0)
    assert all(v >= 0 for v in tw.weights.values())
    assert tw.vol_estimate <= StrategyConfig().target_vol + 1e-9
    risk = {t: w for t, w in tw.weights.items() if t != StrategyConfig().cash}
    assert max(risk.values()) <= StrategyConfig().max_weight + 1e-9


def test_downtrending_assets_are_excluded_and_cash_absorbs():
    drift = {t: -0.002 for t in TICKERS if t != "BIL"}
    tw = compute_target_weights(fake_prices(drift=drift, vol=0.005), pd.Timestamp("2021-06-01"))
    assert not any(tw.eligible.values())
    assert tw.weights["BIL"] == pytest.approx(1.0)


def test_no_lookahead_future_prices_cannot_change_todays_weights():
    p = fake_prices(500)
    asof = p.index[300]
    a = compute_target_weights(p, asof)
    q = p.copy()
    q.iloc[301:] = q.iloc[301:] * 7.0       # wreck the future
    b = compute_target_weights(q, asof)
    assert a.weights == b.weights


def test_needs_enough_history():
    with pytest.raises(ValueError):
        compute_target_weights(fake_prices(100), pd.Timestamp("2020-05-01"))


def test_price_checks_catch_problems():
    p = fake_prices(60)
    assert check_prices(p) == []
    p2 = p.copy()
    p2.iloc[30, 0] = p2.iloc[29, 0] * 3
    p2.iloc[10:20, 1] = p2.iloc[10, 1]
    p2.iloc[5, 2] = -1
    kinds = {i.kind for i in check_prices(p2)}
    assert {"big_move", "stale", "non_positive"} <= kinds
