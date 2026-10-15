"""TWAP execution strategy: split one parent order into 9 child orders, one per bar.

Subclasses `DemoStrategy` from NautilusTrader's official example (LGPL-3.0) and uses only
the public strategy API. Needs `twap.py` (our own) next to it.
"""
from nautilus_trader.model.enums import OrderSide

from strategy import DemoStrategy  # from the official example folder
from twap import twap_schedule


class TwapStrategy(DemoStrategy):
    TOTAL = 10_000   # parent order size (lots)
    SLICES = 9       # one child order per bar

    def on_start(self):
        super().on_start()
        self.plan = twap_schedule(self.TOTAL, self.SLICES)  # e.g. [1112, 1111, ...]

    def on_bar(self, bar):
        super().on_bar(bar)          # counts bars: self.bars_processed = 1, 2, 3 ...
        i = ____                     # TODO 1: index into self.plan for this bar (list starts at 0)
        qty = ____                   # TODO 2: this bar's child quantity, taken from self.plan
        instrument = self.cache.instrument(bar.bar_type.instrument_id)
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=OrderSide.BUY,
            quantity=instrument.make_qty(qty),
        )
        self.submit_order(order)
        self.log.info(f"Child order {i + 1}/{self.SLICES}: BUY {qty}")
