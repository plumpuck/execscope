"""First order strategy: buy on the first bar.

Subclasses `DemoStrategy` from NautilusTrader's official example (LGPL-3.0) and uses only its
public strategy API (`order_factory`, `submit_order`).

Run with the official NautilusTrader example `example_01_load_bars_from_custom_csv`
(develop_v1 branch). Not included here: that example's own files are LGPL-3.0 code.
`quantity` is 1000 for the large-order experiment (first bar volume is only 205).
"""
from nautilus_trader.model.enums import OrderSide

from strategy import DemoStrategy  # from the official example folder


class OrderStrategy(DemoStrategy):
    def on_bar(self, bar):
        super().on_bar(bar)
        if self.bars_processed == 1:
            instrument = self.cache.instrument(bar.bar_type.instrument_id)
            order = self.order_factory.market(
                instrument_id=instrument.id,
                order_side=OrderSide.BUY,
                quantity=instrument.make_qty(1000),
            )
            self.submit_order(order)
            self.log.info(f"Order submitted: {order}")
