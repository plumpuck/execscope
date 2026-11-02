import json
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from execscope.live.broker import IBKRBroker, Order, PaperBroker
from execscope.live.rebalance import in_rebalance_window, plan_orders, run_rebalance
from execscope.live.risk import DrawdownGuard, RiskError, check_plan
from tests.test_portfolio_core import fake_prices

PX = {"SPY": 500.0, "IEF": 100.0, "GLD": 200.0, "BIL": 91.0}


def test_plan_hand_case_whole_shares_sells_first():
    # equity 10_000, 1% buffer -> 9_900 investable. SPY 40% = 3_960 -> 7 shares (3_500). IEF 30% -> 29 shares.
    orders = plan_orders(10_000, {"GLD": 20}, PX, {"SPY": 0.4, "IEF": 0.3, "BIL": 0.3}, "BIL")
    by = {o.symbol: o for o in orders}
    assert by["SPY"].qty == 7 and by["IEF"].qty == 29 and by["GLD"].side == "SELL" and by["GLD"].qty == 20
    assert orders[0].side == "SELL"                                  # sells first
    assert by["SPY"].limit_price == pytest.approx(500 * 1.002)


@settings(max_examples=80, deadline=None)
@given(st.integers(2_000, 50_000), st.lists(st.floats(0, 1), min_size=3, max_size=3))
def test_plan_never_shorts_or_overspends(equity, raw):
    total = sum(raw) or 1.0
    w = [x / total for x in raw]
    target = {"SPY": w[0], "IEF": w[1], "BIL": w[2]}
    orders = plan_orders(equity, {}, PX, target, "BIL")
    spend = sum(o.qty * o.limit_price for o in orders if o.side == "BUY")
    assert spend <= equity + 1e-6 and all(o.qty > 0 for o in orders)


def test_small_trades_and_band_are_skipped():
    orders = plan_orders(10_000, {"SPY": 7, "IEF": 29}, PX, {"SPY": 0.4, "IEF": 0.3, "BIL": 0.3}, "BIL")
    assert [o for o in orders if o.symbol in ("SPY", "IEF")] == []


def test_risk_catches_every_violation():
    o = lambda s, side, q, lim: Order(s, side, q, lim)  # noqa: E731
    pos = {"SPY": 5}
    assert check_plan([o("SPY", "BUY", 3, 501)], 10_000, pos, PX, 5_000) == []
    assert any("allow-list" in v for v in check_plan([o("TSLA", "BUY", 1, 500)], 10_000, pos, {**PX, "TSLA": 500}, 5_000))
    assert any("short" in v for v in check_plan([o("SPY", "SELL", 9, 499)], 10_000, pos, PX, 5_000))
    assert any("limit" in v and "from" in v for v in check_plan([o("SPY", "BUY", 1, 600)], 10_000, pos, PX, 5_000))
    assert any("% of equity" in v for v in check_plan([o("SPY", "BUY", 10, 501)], 10_000, pos, PX, 9_000))
    assert any("cash" in v for v in check_plan([o("IEF", "BUY", 30, 100.1)], 10_000, pos, PX, 1_000))
    assert any("whole number" in v for v in check_plan([o("SPY", "BUY", 0, 500)], 10_000, pos, PX, 5_000))


def test_cash_etf_orders_are_exempt_so_the_kill_switch_can_move_everything_to_cash():
    big = Order("BIL", "BUY", 100, 91.1)       # 91% of equity in the cash ETF must be allowed
    assert check_plan([big], 10_000, {}, PX, 10_000) == []


def test_drawdown_guard_halts_and_stays_halted_until_reset(tmp_path):
    g = DrawdownGuard(str(tmp_path / "dd.json"), limit=0.15)
    assert g.update(10_000) is False and g.update(9_000) is False
    assert g.update(8_400) is True              # -16% from the high
    assert DrawdownGuard(str(tmp_path / "dd.json"), 0.15).update(12_000) is True   # persisted, even after recovery
    g.reset(8_400)
    assert g.update(8_400) is False


def test_paper_broker_fills_and_persists(tmp_path):
    b = PaperBroker(str(tmp_path / "p.json"), 10_000, price_source=lambda s: PX[s])
    r = b.submit(Order("SPY", "BUY", 5, 501))
    assert r.status == "filled" and b.positions() == {"SPY": 5}
    assert b.cash() == pytest.approx(10_000 - 5 * 500 * 1.0002 - r.fee)
    assert PaperBroker(str(tmp_path / "p.json"), price_source=lambda s: PX[s]).positions() == {"SPY": 5}
    assert b.submit(Order("SPY", "SELL", 9, 499)).status == "rejected"
    assert b.submit(Order("SPY", "BUY", 1, 400)).status == "unfilled"          # limit below market
    assert b.submit(Order("SPY", "BUY", 1000, 501)).status == "rejected"       # not enough cash


def make_paper(tmp_path, cash=10_000):
    return PaperBroker(str(tmp_path / "paper.json"), cash, price_source=lambda s: PRICES[s])


PRICES = {"SPY": 500.0, "EFA": 80.0, "EEM": 45.0, "IEF": 95.0, "TLT": 90.0, "GLD": 200.0,
          "DBC": 22.0, "VNQ": 90.0, "UUP": 28.0, "BIL": 91.5}


def uptrend_history():
    p = fake_prices(400, drift={t: 0.0008 for t in PRICES}, vol=0.004)
    p = p.rename(columns={"SGOV": "BIL"}) if "BIL" not in p else p
    p.index = pd.bdate_range(end="2026-10-30", periods=len(p))
    return p


def test_dry_run_sends_nothing(tmp_path):
    b = make_paper(tmp_path)
    rep = run_rebalance(b, uptrend_history(), state_dir=str(tmp_path / "s"), execute=False, today=datetime(2026, 10, 30))
    assert not rep.executed and rep.orders and b.positions() == {}
    assert sum(rep.target.values()) == pytest.approx(1.0)


def test_execute_needs_confirmation_and_the_window(tmp_path):
    b = make_paper(tmp_path)
    h = uptrend_history()
    with pytest.raises(RiskError, match="window"):
        run_rebalance(b, h, state_dir=str(tmp_path / "s"), execute=True, confirm=lambda t: True, today=datetime(2026, 10, 12))
    rep = run_rebalance(b, h, state_dir=str(tmp_path / "s"), execute=True, confirm=lambda t: False, today=datetime(2026, 10, 30))
    assert not rep.executed and b.positions() == {}
    rep = run_rebalance(b, h, state_dir=str(tmp_path / "s"), execute=True, confirm=lambda t: True, today=datetime(2026, 10, 30))
    assert rep.executed and rep.results and b.positions()
    with pytest.raises(RiskError, match="window"):          # already rebalanced this month
        run_rebalance(b, h, state_dir=str(tmp_path / "s"), execute=True, confirm=lambda t: True, today=datetime(2026, 10, 31))
    assert (tmp_path / "s" / "orders.csv").read_text().count("\n") == len(rep.results) + 1


def test_stale_prices_are_refused(tmp_path):
    with pytest.raises(RiskError, match="old"):
        run_rebalance(make_paper(tmp_path), uptrend_history(), state_dir=str(tmp_path / "s"), today=datetime(2026, 11, 20))


def test_kill_switch_moves_everything_to_cash(tmp_path):
    b = make_paper(tmp_path)
    b.state["positions"] = {"SPY": 6, "IEF": 20}
    b.state["cash"] = 3_000.0
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "drawdown.json").write_text(json.dumps({"hwm": 20_000.0, "halted": False}))   # equity ~ 7_900 -> -60%
    rep = run_rebalance(b, uptrend_history(), state_dir=str(sd), execute=True, confirm=lambda t: True,
                        today=datetime(2026, 10, 30))
    assert rep.halted and rep.executed
    assert set(b.positions()) <= {"BIL"} and b.positions().get("BIL", 0) > 0


def test_rebalance_window_logic():
    assert in_rebalance_window(datetime(2026, 10, 29), None) and in_rebalance_window(datetime(2026, 10, 30), "2026-09")
    assert not in_rebalance_window(datetime(2026, 10, 15), None)
    assert not in_rebalance_window(datetime(2026, 10, 30), "2026-10")


class FakeIB:
    def __init__(self, fill=True):
        self.fill, self.sent, self.cancelled = fill, [], 0

    def positions(self):
        return [SimpleNamespace(account="DU1", contract=SimpleNamespace(symbol="SPY"), position=3.0)]

    def accountSummary(self):
        return [SimpleNamespace(tag="NetLiquidation", value="9500.5", currency="USD", account="DU1"),
                SimpleNamespace(tag="TotalCashValue", value="1200.25", currency="USD", account="DU1")]

    def qualifyContracts(self, c):
        return [c]

    def reqMktData(self, c, *a):
        return SimpleNamespace(marketPrice=lambda: 501.25)

    def cancelMktData(self, c):
        pass

    def sleep(self, s):
        pass

    def placeOrder(self, c, o):
        self.sent.append((c, o))
        st = SimpleNamespace(filled=o[2] if self.fill else 0, avgFillPrice=501.0, status="Filled" if self.fill else "Submitted")
        return SimpleNamespace(orderStatus=st, order=o, isDone=lambda: self.fill)

    def cancelOrder(self, o):
        self.cancelled += 1


def ib_broker(fill=True, port=7497):
    return IBKRBroker(port=port, ib=FakeIB(fill), contract_factory=lambda s: s,
                      order_factory=lambda side, qty, px: (side, px, qty), account="DU1", fill_timeout=2)


def test_ibkr_adapter_reads_account_and_sends_limit_orders():
    b = ib_broker()
    assert b.positions() == {"SPY": 3} and b.cash() == 1200.25 and b.equity({}) == 9500.5
    assert b.prices(["SPY"]) == {"SPY": 501.25}
    r = b.submit(Order("SPY", "BUY", 2, 502.0))
    assert r.status == "filled" and r.filled == 2 and b.ib.sent[0][1][:2] == ("BUY", 502.0)


def test_ibkr_unfilled_order_is_cancelled_and_ports_classify_paper_vs_live():
    b = ib_broker(fill=False)
    r = b.submit(Order("SPY", "BUY", 2, 502.0))
    assert r.status == "unfilled" and b.ib.cancelled == 1
    assert ib_broker(port=7497).is_paper and ib_broker(port=4002).is_paper
    assert not ib_broker(port=7496).is_paper and not ib_broker(port=4001).is_paper
