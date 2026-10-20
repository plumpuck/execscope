"""Execution strategies for NautilusTrader: execute one parent order as one-shot or TWAP child orders.

Written against NautilusTrader's public strategy API only (no example code copied).
Importing this module requires `nautilus_trader`.

Conventions
-----------
* The parent order is released on the first bar. `arrival_price` = close of that bar,
  `decision_price` = `arrival_price` (zero delay) unless the caller overrides it later.
* `end_price` = close of the last bar seen, used for the opportunity cost of unfilled quantity.
* `bar_log` keeps (typical price, volume) per bar, for interval-VWAP benchmarks.
"""
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.trading.strategy import Strategy

from execscope.algos.twap import twap_schedule


class ExecConfig(StrategyConfig, frozen=True):
    bar_type: str
    side: str = "BUY"          # "BUY" or "SELL"
    total_qty: int = 10_000    # parent order size in contracts
    mode: str = "twap"         # "twap" or "oneshot"
    n_slices: int = 9          # TWAP: number of child orders, one per bar


class ExecStrategy(Strategy):
    def __init__(self, config: ExecConfig) -> None:
        super().__init__(config)
        if config.side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if config.mode not in ("twap", "oneshot"):
            raise ValueError("mode must be 'twap' or 'oneshot'")
        self.bar_type = BarType.from_str(config.bar_type)
        self.order_side = OrderSide.BUY if config.side == "BUY" else OrderSide.SELL
        self.bars_seen = 0
        self.arrival_price: float | None = None
        self.end_price: float | None = None
        self.fills: list[tuple[float, float]] = []   # (qty, price)
        self.bar_log: list[tuple[float, float]] = []  # (typical price, volume)
        self.plan: list[int] = []

    def on_start(self) -> None:
        if self.config.mode == "twap":
            self.plan = twap_schedule(self.config.total_qty, self.config.n_slices)
        else:
            self.plan = [self.config.total_qty]
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar) -> None:
        self.bars_seen += 1
        close = bar.close.as_double()
        self.end_price = close
        typical = (bar.high.as_double() + bar.low.as_double() + close) / 3
        self.bar_log.append((typical, bar.volume.as_double()))
        if self.arrival_price is None:
            self.arrival_price = close

        index = self.bars_seen - 1
        if index >= len(self.plan):
            return  # parent order fully released
        instrument = self.cache.instrument(bar.bar_type.instrument_id)
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=self.order_side,
            quantity=instrument.make_qty(self.plan[index]),
        )
        self.submit_order(order)

    def on_order_filled(self, event: OrderFilled) -> None:
        self.fills.append((event.last_qty.as_double(), event.last_px.as_double()))
