import pandas as pd
import pytest

from execscope.data.binance import klines_to_bars, read_binance, trades_to_bars, write_bars_csv
from execscope.data.synthetic import synthetic_minute_bars, synthetic_trades
from execscope.experiments.granularity import bar_vwap, granularity_bias, true_vwap


def _write_trades(tmp_path, header, unit):
    bars = synthetic_minute_bars(n_days=1, seed=4).iloc[:10]
    tape = synthetic_trades(bars, trades_per_bar=5, seed=1)
    epoch = tape.index.as_unit(unit).astype("int64")
    raw = pd.DataFrame({"a": tape["agg_trade_id"].to_numpy(), "p": tape["price"].to_numpy(),
                        "q": tape["quantity"].to_numpy(), "f": tape["first_trade_id"].to_numpy(),
                        "l": tape["last_trade_id"].to_numpy(), "t": epoch.to_numpy(),
                        "m": ["True" if x else "False" for x in tape["is_buyer_maker"]]})
    path = tmp_path / "aggTrades.csv"
    if header:
        raw.columns = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
                       "transact_time", "is_buyer_maker"]
    raw.to_csv(path, index=False, header=header)
    return path, tape


@pytest.mark.parametrize("header", [True, False])
@pytest.mark.parametrize("unit", ["ms", "us"])
def test_read_aggtrades_handles_header_and_time_unit(tmp_path, header, unit):
    path, tape = _write_trades(tmp_path, header, unit)
    got = read_binance(str(path), "aggTrades")
    assert len(got) == len(tape)
    assert got.index.min().floor("ms") == tape.index.min().floor("ms")
    assert got["price"].iloc[0] == pytest.approx(tape["price"].iloc[0])
    assert got["is_buyer_maker"].dtype == bool


def test_read_klines_and_roundtrip_csv(tmp_path):
    bars = synthetic_minute_bars(n_days=1, seed=5).iloc[:5]
    epoch = bars.index.as_unit("ms").astype("int64").to_numpy()
    k = pd.DataFrame({"t": epoch, "o": bars["open"].to_numpy(), "h": bars["high"].to_numpy(), "l": bars["low"].to_numpy(),
                      "c": bars["close"].to_numpy(), "v": bars["volume"].to_numpy(), "ct": epoch + 59_999,
                      "qv": 1.0, "n": 10, "tb": 1.0, "tq": 1.0, "ig": 0})
    p = tmp_path / "k.csv"
    k.to_csv(p, index=False, header=False)
    out = klines_to_bars(read_binance(str(p), "klines"))
    assert out["close"].tolist() == pytest.approx(bars["close"].tolist())
    csv = tmp_path / "bars.csv"
    write_bars_csv(out, str(csv))
    from execscope.backtest.runner import load_bars_csv
    back = load_bars_csv(str(csv))
    assert back["close"].tolist() == pytest.approx(out["close"].tolist())


def test_bad_timestamp_and_kind_rejected(tmp_path):
    p = tmp_path / "x.csv"
    pd.DataFrame([[1, 2.0, 1.0, 1, 1, 12345, "True"]]).to_csv(p, index=False, header=False)
    with pytest.raises(ValueError):
        read_binance(str(p), "aggTrades")
    with pytest.raises(ValueError):
        read_binance(str(p), "orderbook")


def test_trades_to_bars_matches_source_bars():
    bars = synthetic_minute_bars(n_days=1, seed=6).iloc[:8]
    rebuilt = trades_to_bars(synthetic_trades(bars, trades_per_bar=30, seed=2))
    assert len(rebuilt) == len(bars)
    assert (rebuilt["high"] <= bars["high"] + 1e-9).all() and (rebuilt["low"] >= bars["low"] - 1e-9).all()
    assert rebuilt["volume"].tolist() == pytest.approx(bars["volume"].tolist())


def test_true_vwap_hand_case_and_bias_table():
    t = pd.DataFrame({"price": [100.0, 102.0], "quantity": [1.0, 3.0]},
                     index=pd.to_datetime(["2024-01-01 00:00:10", "2024-01-01 00:00:20"]))
    assert true_vwap(t) == pytest.approx(101.5)
    bars = synthetic_minute_bars(n_days=1, seed=7).iloc[:40]
    tape = synthetic_trades(bars, trades_per_bar=25, seed=3)
    starts = [bars.index[5], bars.index[15]]
    res = granularity_bias(tape, starts, horizon_minutes=10)
    assert len(res) == 2 and (res["first_bar_range_bps"] >= 0).all()
    assert bar_vwap(bars.iloc[5:15]) > 0


def test_prepare_klines_concatenates_files_and_writes_csv(tmp_path, capsys):
    from execscope.data.prepare import main

    bars = synthetic_minute_bars(n_days=1, seed=8).iloc[:10]
    paths = []
    for name, part in (("a.csv", bars.iloc[:5]), ("b.csv", bars.iloc[5:])):
        epoch = part.index.as_unit("ms").astype("int64").to_numpy()
        k = pd.DataFrame({"t": epoch, "o": part["open"].to_numpy(), "h": part["high"].to_numpy(), "l": part["low"].to_numpy(),
                          "c": part["close"].to_numpy(), "v": part["volume"].to_numpy(), "ct": epoch + 59_999,
                          "qv": 1.0, "n": 10, "tb": 1.0, "tq": 1.0, "ig": 0})
        p = tmp_path / name
        k.to_csv(p, index=False, header=False)
        paths.append(str(p))
    out = tmp_path / "bars.csv"
    main(["klines", paths[1], paths[0], "--out", str(out)])      # files given out of order
    from execscope.backtest.runner import load_bars_csv
    back = load_bars_csv(str(out))
    assert len(back) == 10 and back.index.is_monotonic_increasing
    assert "data quality: clean" in capsys.readouterr().out
