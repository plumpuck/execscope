import json

import pytest

pytest.importorskip("nautilus_trader")
from execscope.data.synthetic import synthetic_minute_bars, synthetic_trades  # noqa: E402
from execscope.experiments.cli import main  # noqa: E402

FAST = ["--parents", "3", "--horizon", "10", "--qty", "50", "--boot", "100"]


@pytest.mark.parametrize("exp", ["e1", "e2", "e3", "e5"])
def test_named_experiments_run_and_write_json(tmp_path, exp):
    main([exp, *FAST, "--out", str(tmp_path)])
    files = list(tmp_path.rglob("*.json"))
    assert files, exp
    for f in files:
        json.loads(f.read_text())


def test_e4_reads_a_binance_style_tape(tmp_path):
    bars = synthetic_minute_bars(n_days=1, seed=9).iloc[:120]
    tape = synthetic_trades(bars, trades_per_bar=8, seed=1)
    epoch = tape.index.as_unit("ms").astype("int64")
    import pandas as pd
    raw = pd.DataFrame({"a": tape["agg_trade_id"].to_numpy(), "p": tape["price"].to_numpy(), "q": tape["quantity"].to_numpy(),
                        "f": tape["first_trade_id"].to_numpy(), "l": tape["last_trade_id"].to_numpy(),
                        "t": epoch.to_numpy(), "m": ["False"] * len(tape)})
    p = tmp_path / "aggTrades.csv"
    raw.to_csv(p, index=False, header=False)
    main(["e4", "--trades", str(p), "--parents", "3", "--horizon", "10", "--boot", "100", "--out", str(tmp_path / "out")])
    saved = json.loads((tmp_path / "out" / "e4.json").read_text())
    assert saved["n"] >= 1 and (tmp_path / "out" / "e4_rows.csv").exists()
    entry = saved["summary"]["first_bar_range_bps"]
    assert entry["ci_low"] <= entry["mean"] <= entry["ci_high"]


def test_e4_pools_several_days_from_a_wildcard(tmp_path):
    import pandas as pd
    for day, seed in (("2024-01-02", 1), ("2024-01-03", 2)):
        idx = pd.date_range(f"{day} 00:00:05", periods=120, freq="1min")
        raw = pd.DataFrame({"a": range(120), "p": [100.0 + seed] * 120, "q": [1.0] * 120, "f": range(120), "l": range(120),
                            "t": idx.as_unit("ms").astype("int64"), "m": ["False"] * 120})
        raw.to_csv(tmp_path / f"t-{day}.csv", index=False, header=False)
    main(["e4", "--trades", str(tmp_path / "t-*.csv"), "--parents", "100", "--horizon", "10", "--boot", "50", "--out", str(tmp_path / "out")])
    saved = json.loads((tmp_path / "out" / "e4.json").read_text())
    assert saved["n"] == saved["windows_available"] and saved["first_start"].startswith("2024-01-02")
    assert saved["last_start"].startswith("2024-01-03") and len(saved["manifest"]["data"].split(",")) == 2


def _bars_with_a_jump(tmp_path):
    from execscope.data.binance import write_bars_csv
    bars = synthetic_minute_bars(n_days=2, seed=3).copy()
    bars.iloc[1500:, bars.columns.get_indexer(["open", "high", "low", "close"])] *= 1.05
    path = tmp_path / "bars.csv"
    write_bars_csv(bars, str(path))
    return str(path)


def test_quality_finding_stops_the_run_until_it_is_accepted_and_recorded(tmp_path):
    data = _bars_with_a_jump(tmp_path)
    with pytest.raises(ValueError, match="return_outliers"):
        main(["e1", "--data", data, *FAST, "--out", str(tmp_path / "a")])
    main(["e1", "--data", data, *FAST, "--out", str(tmp_path / "b"), "--allow-quality", "return_outliers"])
    man = json.loads((tmp_path / "b" / "e1" / "manifest.json").read_text())
    assert "return_outliers" in man["config"]["quality_allow"]


def test_sweep_runs_can_be_loaded_into_the_store(tmp_path):
    from execscope.service import db
    from execscope.service.ingest import main as ingest
    main(["e5", *FAST, "--out", str(tmp_path)])
    assert (tmp_path / "e5__default" / "manifest.json").exists()
    store = tmp_path / "store.db"
    ingest([str(tmp_path / "e5*"), "--db", str(store)])    # e5.json is a file, not a run: ignored
    conn = db.connect(str(store))
    names = [e["name"] for e in db.list_experiments(conn)]
    assert "e5__default" in names and "e5__side_SELL" in names
    assert db.leaderboard(conn, db.list_experiments(conn)[0]["id"])
    ingest([str(tmp_path / "e5*"), "--db", str(store)])    # second load adds nothing
    assert len(db.list_experiments(conn)) == len(names)
    conn.close()
