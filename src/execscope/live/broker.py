"""Broker interface with a paper broker (fully tested) and an Interactive Brokers adapter.

IBKRBroker is written against the `ib_async` package (`pip install ib_async`) and TWS / IB Gateway.
It has been tested only against a fake IB object, NEVER against a real IB session: run it on a PAPER
account first and read every line it prints.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str            # "BUY" | "SELL"
    qty: int
    limit_price: float


@dataclass(frozen=True)
class OrderResult:
    symbol: str
    side: str
    requested: int
    filled: int
    avg_price: float
    status: str          # "filled" | "partial" | "unfilled" | "rejected"
    fee: float = 0.0


class Broker(Protocol):
    name: str
    is_paper: bool

    def positions(self) -> dict[str, int]: ...
    def cash(self) -> float: ...
    def equity(self, prices: dict[str, float]) -> float: ...
    def prices(self, symbols: list[str]) -> dict[str, float]: ...
    def submit(self, order: Order) -> OrderResult: ...


class PaperBroker:
    """Simulated account kept in a JSON file. Marketable limit orders fill at the reference price plus
    slippage; commission = max(min_fee, per_share * qty). Costs are ASSUMPTIONS, not your real fees."""

    name = "paper"
    is_paper = True

    def __init__(self, path: str, start_cash: float = 10_000.0, price_source=None,
                 slippage_bps: float = 2.0, per_share: float = 0.005, min_fee: float = 1.0):
        self.path = Path(path)
        self.price_source = price_source
        self.slippage_bps, self.per_share, self.min_fee = slippage_bps, per_share, min_fee
        self.state: dict[str, Any] = (
            json.loads(self.path.read_text()) if self.path.exists() else {"cash": start_cash, "positions": {}}
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def positions(self) -> dict[str, int]:
        return {k: int(v) for k, v in self.state["positions"].items() if v}

    def cash(self) -> float:
        return float(self.state["cash"])

    def prices(self, symbols: list[str]) -> dict[str, float]:
        if self.price_source is None:
            raise RuntimeError("PaperBroker needs a price_source")
        return {s: float(self.price_source(s)) for s in symbols}

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash() + sum(q * prices[s] for s, q in self.positions().items())

    def submit(self, order: Order) -> OrderResult:
        ref = self.prices([order.symbol])[order.symbol]
        slip = self.slippage_bps / 10_000
        px = ref * (1 + slip) if order.side == "BUY" else ref * (1 - slip)
        if (order.side == "BUY" and px > order.limit_price) or (order.side == "SELL" and px < order.limit_price):
            return OrderResult(order.symbol, order.side, order.qty, 0, 0.0, "unfilled")
        fee = max(self.min_fee, self.per_share * order.qty)
        have = self.positions().get(order.symbol, 0)
        if order.side == "SELL" and order.qty > have:
            return OrderResult(order.symbol, order.side, order.qty, 0, 0.0, "rejected")
        cost = order.qty * px
        if order.side == "BUY" and cost + fee > self.cash() + 1e-9:
            return OrderResult(order.symbol, order.side, order.qty, 0, 0.0, "rejected")
        sign = 1 if order.side == "BUY" else -1
        self.state["cash"] = self.cash() - sign * cost - fee
        self.state["positions"][order.symbol] = have + sign * order.qty
        self._save()
        return OrderResult(order.symbol, order.side, order.qty, order.qty, px, "filled", fee)


PAPER_PORTS = {7497, 4002}     # default TWS paper / IB Gateway paper ports
LIVE_PORTS = {7496, 4001}      # default TWS live / IB Gateway live ports


class IBKRBroker:
    """Interactive Brokers via ib_async. `ib` can be injected for tests."""

    name = "ibkr"

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 17, account: str | None = None,
                 ib=None, contract_factory=None, order_factory=None, fill_timeout: float = 30.0):
        if ib is None:                                   # pragma: no cover - needs the real package
            try:
                from ib_async import IB, LimitOrder, Stock
            except ImportError as exc:
                raise ImportError("pip install ib_async") from exc
            ib = IB()
            contract_factory = contract_factory or (lambda s: Stock(s, "SMART", "USD"))
            order_factory = order_factory or (lambda side, qty, px: LimitOrder(side, qty, px, tif="DAY"))
            ib.connect(host, port, clientId=client_id)
        self.ib, self.account, self.port = ib, account, port
        self.contract_factory, self.order_factory, self.fill_timeout = contract_factory, order_factory, fill_timeout
        self.is_paper = port in PAPER_PORTS

    def positions(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.ib.positions():
            if self.account and p.account != self.account:
                continue
            if p.position:
                out[p.contract.symbol] = out.get(p.contract.symbol, 0) + int(p.position)
        return out

    def _summary(self, tag: str) -> float:
        for v in self.ib.accountSummary():
            if v.tag == tag and v.currency in ("USD", "BASE") and (not self.account or v.account == self.account):
                return float(v.value)
        raise RuntimeError(f"account summary has no {tag} in USD; check the account currency")

    def cash(self) -> float:
        return self._summary("TotalCashValue")

    def equity(self, prices: dict[str, float]) -> float:
        return self._summary("NetLiquidation")

    def prices(self, symbols: list[str]) -> dict[str, float]:
        out = {}
        for s in symbols:
            c = self.contract_factory(s)
            self.ib.qualifyContracts(c)
            t = self.ib.reqMktData(c, "", False, False)
            self.ib.sleep(2)
            px = t.marketPrice()
            if px is None or (isinstance(px, float) and math.isnan(px)) or px <= 0:
                raise RuntimeError(f"no price for {s} (market closed or no market-data subscription?)")
            out[s] = float(px)
            self.ib.cancelMktData(c)
        return out

    def submit(self, order: Order) -> OrderResult:
        c = self.contract_factory(order.symbol)
        self.ib.qualifyContracts(c)
        trade = self.ib.placeOrder(c, self.order_factory(order.side, order.qty, round(order.limit_price, 2)))
        waited = 0.0
        while not trade.isDone() and waited < self.fill_timeout:
            self.ib.sleep(1)
            waited += 1
        st = trade.orderStatus
        filled = int(st.filled)
        if filled >= order.qty:
            status = "filled"
        elif filled > 0:
            status = "partial"
        else:
            status = "rejected" if st.status in ("Cancelled", "Inactive", "ApiCancelled") else "unfilled"
        if not trade.isDone():
            self.ib.cancelOrder(trade.order)
        return OrderResult(order.symbol, order.side, order.qty, filled, float(st.avgFillPrice or 0.0), status)

    def disconnect(self) -> None:
        self.ib.disconnect()
