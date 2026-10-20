import pandas as pd
import pytest

from execscope.data.quality import assert_clean, check_bars
from execscope.stats.bootstrap import bootstrap_ci, paired_diff_ci, sign_test_p
from execscope.tca.benchmarks import benchmark_report, participation_rate, slippage_vs


def test_bootstrap_is_seeded_and_covers_mean():
    v = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    a = bootstrap_ci(v, seed=1)
    assert a == bootstrap_ci(v, seed=1)
    est, lo, hi = a
    assert est == pytest.approx(4.5) and lo < est < hi


def test_paired_diff_detects_consistent_improvement():
    base = [10.0, 12.0, 9.0, 11.0, 13.0, 10.5, 12.5, 9.5]
    better = [x - 2 for x in base]
    est, lo, hi = paired_diff_ci(base, better, seed=3)
    assert est == pytest.approx(2.0) and lo > 0   # whole interval above 0
    assert sign_test_p([x - y for x, y in zip(base, better)]) < 0.01


def test_sign_test_no_evidence_when_balanced():
    assert sign_test_p([1, -1, 1, -1]) == 1.0
    assert sign_test_p([0, 0]) == 1.0


def _bars(n=30):
    idx = pd.date_range("2024-01-02 09:00", periods=n, freq="1min")
    close = pd.Series([1.10 + 0.0001 * (i % 5) for i in range(n)], index=idx)
    return pd.DataFrame({"open": close, "high": close + 0.0001, "low": close - 0.0001,
                         "close": close, "volume": 100.0})


def test_clean_data_has_no_issues():
    assert check_bars(_bars()) == []
    assert_clean(_bars())


def test_detects_gap_duplicate_and_bad_ohlc():
    df = _bars()
    gapped = df.drop(df.index[10:13])
    assert any(i.kind == "gaps" and "3 missing" in i.detail for i in check_bars(gapped))
    dup = pd.concat([df, df.iloc[[5]]])
    assert any(i.kind == "duplicate_timestamps" for i in check_bars(dup))
    bad = df.copy()
    bad.iloc[4, bad.columns.get_loc("high")] = 0.5
    assert any(i.kind == "ohlc_inconsistent" for i in check_bars(bad))
    with pytest.raises(ValueError):
        assert_clean(bad)


def test_detects_outlier_return_and_zero_volume():
    df = _bars()
    df.iloc[15, df.columns.get_loc("close")] = 2.0
    df.iloc[15, df.columns.get_loc("high")] = 2.0
    df.iloc[20, df.columns.get_loc("volume")] = 0.0
    kinds = {i.kind for i in check_bars(df)}
    assert {"return_outliers", "zero_volume"} <= kinds


def test_benchmarks():
    assert slippage_vs(1.1002, 1.1000, "BUY") == pytest.approx(0.0002 / 1.1 * 1e4)
    assert slippage_vs(1.1002, 1.1000, "SELL") < 0
    assert participation_rate(100, 1000) == pytest.approx(0.1)
    r = benchmark_report([(100, 1.1002)], "BUY", 1.1000, 1.1001, 1.1003, 5000)
    assert r["vs_close_bps"] < 0 < r["vs_arrival_bps"]
    assert r["participation"] == pytest.approx(0.02)
