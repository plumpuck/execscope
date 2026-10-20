import json

import pytest

pytest.importorskip("nautilus_trader")
from execscope.data.synthetic import synthetic_minute_bars  # noqa: E402
from execscope.experiments.harness import (  # noqa: E402
    ExperimentConfig,
    choose_starts,
    profile_before,
    run_experiment,
    save,
)


def small_cfg(**kw):
    base = dict(name="t", n_parents=4, horizon_bars=10, qty=50, n_boot=200,
                algos=[{"name": "oneshot"}, {"name": "twap"}, {"name": "vwap"}])
    base.update(kw)
    return ExperimentConfig(**base)


def test_choose_starts_non_overlapping_and_seeded():
    s = choose_starts(5000, 30, 10, seed=1, warmup=100)
    assert s == choose_starts(5000, 30, 10, seed=1, warmup=100)
    assert all(b - a >= 30 for a, b in zip(s, s[1:], strict=False))
    with pytest.raises(ValueError):
        choose_starts(200, 30, 50, seed=1, warmup=100)


def test_profile_uses_only_earlier_days():
    df = synthetic_minute_bars(n_days=3, seed=1)
    t0 = df.index[1440 + 100]
    prof = profile_before(df, t0, 10)
    assert prof is not None and len(prof) == 10 and abs(sum(prof) - 1) < 1e-9
    assert profile_before(df, df.index[100], 10) is None   # day 1: no history yet


def test_experiment_runs_is_paired_and_deterministic():
    t1, s1, m1 = run_experiment(small_cfg())
    t2, s2, _ = run_experiment(small_cfg())
    assert t1.equals(t2) and s1 == s2
    assert set(t1["label"]) == {"oneshot", "twap", "vwap"}
    assert (t1["filled_qty"] == t1["target_qty"]).all()
    assert set(s1["paired_vs_baseline"]) == {"twap", "vwap"}
    d = s1["paired_vs_baseline"]["twap"]["vs_vwap_bps"]
    assert d["ci_low"] <= d["mean_diff"] <= d["ci_high"]
    assert m1["config"]["seed"] == 0 and m1["data"] == "synthetic:0"


def test_save_writes_three_files(tmp_path):
    cfg = small_cfg()
    table, summary, man = run_experiment(cfg)
    out = save(cfg, table, summary, man, str(tmp_path))
    assert {p.name for p in out.iterdir()} == {"rows.csv", "summary.json", "manifest.json"}
    assert json.loads((out / "summary.json").read_text())["algos"]["twap"]["n"] == 4
