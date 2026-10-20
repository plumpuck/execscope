import pytest

pytest.importorskip("nautilus_trader")
from execscope.data.synthetic import synthetic_minute_bars  # noqa: E402
from execscope.experiments.fidelity import FidelityConfig, run_fidelity, summarise_fidelity, window_sigma_bps  # noqa: E402
from execscope.experiments.harness import ExperimentConfig, choose_starts  # noqa: E402
from execscope.experiments.sweeps import cost_shift_table, run_variants  # noqa: E402


def test_fidelity_default_model_understates_large_orders():
    df = synthetic_minute_bars(n_days=3, seed=2)
    starts = choose_starts(len(df), 10, 6, seed=0, warmup=1440)
    cfg = FidelityConfig(sizes=(1, 60), n_boot=200)
    t = run_fidelity(df, starts, 10, cfg)
    s = summarise_fidelity(t, cfg)
    small, big = s[1], s[60]
    # Nautilus caps slippage at ~1 tick, the depth-walking reference keeps growing with size
    assert big["refsim_bps"]["mean"] > small["refsim_bps"]["mean"]
    assert big["understatement_vs_refsim_bps"]["mean"] > small["understatement_vs_refsim_bps"]["mean"]
    assert big["nautilus_bps"]["mean"] < big["refsim_bps"]["mean"]


def test_window_sigma_is_zero_for_flat_prices():
    df = synthetic_minute_bars(n_days=1, seed=3).iloc[:20].copy()
    df["close"] = 100.0
    assert window_sigma_bps(df) == 0.0


def test_sweeps_same_parents_and_shift_table():
    base = ExperimentConfig(name="sw", n_parents=3, horizon_bars=10, qty=50, n_boot=100,
                            algos=[{"name": "oneshot"}, {"name": "twap"}])
    res = run_variants(base, {"slip": {"venue": {"prob_slippage": 1.0}}})
    assert set(res) == {"default", "slip"}
    table = cost_shift_table(res, "oneshot")
    row = {r["variant"]: r for r in table}
    assert row["default"]["shift_vs_default"] == 0.0
    assert row["slip"]["shift_vs_default"] >= 0.0   # certain extra slippage cannot make a BUY cheaper
