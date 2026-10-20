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
    main(["e4", "--trades", str(p), "--parents", "3", "--horizon", "10", "--out", str(tmp_path / "out")])
    assert json.loads((tmp_path / "out" / "e4.json").read_text())["n"] >= 1
