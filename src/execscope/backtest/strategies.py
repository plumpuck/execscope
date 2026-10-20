"""Execution strategy for NautilusTrader: release one parent order as child market orders.

Written against NautilusTrader's public strategy API only (no example code copied).
Importing this module requires `nautilus_trader`.

Two release styles:
  * schedule: a precomputed list of child sizes, one per bar (TWAP, VWAP-profile, Almgren-Chriss, one-shot)
  * pov:      each bar, trade `pov_rate` x that bar's volume (capped by what is left)

Conventions
-----------
* The parent order starts on the first bar. `arrival_price` = close of that bar (the decision is
  taken when the bar closes, so this is the last price we could have seen).
* `end_price` = close of the last bar seen, used for the opportunity cost of unfilled quantity.
* `bar_log` keeps (typical price, volume) per bar for interval-VWAP benchmarks.
"""
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.trading.strategy import Strategy

from execscope.algos.schedules import pov_child_qty


class ExecConfig(StrategyConfig, frozen=True):
    bar_type: str
    side: str = "BUY"                   # "BUY" or "SELL"
    total_qty: int = 10_000             # parent order size
    schedule: tuple[int, ...] = ()      # child sizes per bar; empty + pov_rate=0 -> invalid
    pov_rate: float = 0.0               # > 0 switches to participation-of-volume mode


class ExecStrategy(Strategy):
    def __init__(self, config: ExecConfig) -> None:
        super().__init__(config)
        if config.side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if config.pov_rate > 0:
            if config.schedule:
                raise ValueError("use either schedule or pov_rate, not both")
        elif sum(config.schedule) != config.total_qty:
            raise ValueError("schedule must sum to total_qty")
        self.bar_type = BarType.from_str(config.bar_type)
        self.order_side = OrderSide.BUY if config.side == "BUY" else OrderSide.SELL
        self.bars_seen = 0
        self.submitted = 0
        self.arrival_price: float | None = None
        self.end_price: float | None = None
        self.fills: list[tuple[float, float]] = []    # (qty, price)
        self.bar_log: list[tuple[float, float]] = []  # (typical price, volume)

    def on_start(self) -> None:
        self.subscribe_bars(self.bar_type)

    def _child_qty(self, index: int, bar_volume: float) -> int:
        cfg = self.config
        if cfg.pov_rate > 0:
            return pov_child_qty(cfg.total_qty - self.submitted, bar_volume, cfg.pov_rate)
        return cfg.schedule[index] if index < len(cfg.schedule) else 0

    def on_bar(self, bar: Bar) -> None:
        self.bars_seen += 1
        close = bar.close.as_double()
        volume = bar.volume.as_double()
        self.end_price = close
        self.bar_log.append(((bar.high.as_double() + bar.low.as_double() + close) / 3, volume))
        if self.arrival_price is None:
            self.arrival_price = close

        qty = self._child_qty(self.bars_seen - 1, volume)
        if qty <= 0:
            return
        instrument = self.cache.instrument(bar.bar_type.instrument_id)
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=self.order_side,
            quantity=instrument.make_qty(qty),
        )
        self.submitted += qty
        self.submit_order(order)

    def on_order_filled(self, event: OrderFilled) -> None:
        self.fills.append((event.last_qty.as_double(), event.last_px.as_double()))
