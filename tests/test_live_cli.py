import pytest

from execscope.live.cli import LIVE_PHRASE, ensure_live_allowed, main
from execscope.live.risk import RiskError
from execscope.portfolio.data import load_prices_csv
from tests.test_live import uptrend_history


def test_real_money_needs_flag_env_and_typed_sentence():
    ensure_live_allowed(True, False, {}, "")                      # paper: always fine
    with pytest.raises(RiskError, match="understand"):
        ensure_live_allowed(False, False, {"EXECSCOPE_ALLOW_LIVE": "1"}, LIVE_PHRASE)
    with pytest.raises(RiskError, match="ALLOW_LIVE"):
        ensure_live_allowed(False, True, {}, LIVE_PHRASE)
    with pytest.raises(RiskError, match="exactly"):
        ensure_live_allowed(False, True, {"EXECSCOPE_ALLOW_LIVE": "1"}, "yes")
    ensure_live_allowed(False, True, {"EXECSCOPE_ALLOW_LIVE": "1"}, LIVE_PHRASE)


@pytest.fixture
def prices_csv(tmp_path):
    p = uptrend_history()
    path = tmp_path / "prices.csv"
    p.to_csv(path)
    return str(path)


def test_signal_prints_weights_and_orders(prices_csv, capsys):
    main(["signal", "--prices", prices_csv, "--equity", "8000"])
    out = capsys.readouterr().out
    assert "signal as of" in out and "whole-share orders" in out and "BUY" in out


def test_backtest_command_writes_files_and_prints_intervals(prices_csv, tmp_path, capsys):
    main(["backtest", "--prices", prices_csv, "--out", str(tmp_path / "bt")])
    out = capsys.readouterr().out
    assert "strategy" in out and "Sharpe difference" in out or "strategy" in out
    assert (tmp_path / "bt" / "equity.csv").exists() and (tmp_path / "bt" / "backtest.json").exists()


def test_paper_dry_run_then_nothing_is_sent(prices_csv, tmp_path, capsys):
    main(["paper", "--prices", prices_csv, "--state-dir", str(tmp_path / "st"), "--equity", "9000"])
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "plan:" in out


def test_missing_columns_are_reported(tmp_path):
    path = tmp_path / "bad.csv"
    uptrend_history()[["SPY"]].to_csv(path)
    with pytest.raises(SystemExit, match="missing columns"):
        main(["signal", "--prices", str(path), "--equity", "1000"])
    assert len(load_prices_csv(str(path))) > 0
