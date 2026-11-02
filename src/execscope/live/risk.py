"""Pre-trade risk checks and the drawdown kill switch. These are the last line of defence: every limit
here is checked in code, not just documented.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

CASH_SYMBOLS = frozenset({"BIL", "SGOV"})


class RiskError(Exception):
    """Raised when an order plan breaks a limit; nothing is sent to the broker."""


@dataclass(frozen=True)
class RiskLimits:
    max_position_weight: float = 0.40          # one ETF may not exceed 40% of equity after the trade
    max_order_fraction: float = 0.45           # one order may not exceed 45% of equity
    max_orders: int = 20
    max_limit_distance: float = 0.01           # limit price may sit at most 1% from the reference price
    max_drawdown_halt: float = 0.15            # halt and go to cash if equity falls 15% below its high
    min_cash_buffer: float = 0.01              # keep 1% of equity un-invested for fees and rounding
    allowed_symbols: frozenset[str] = field(default_factory=lambda: frozenset(
        {"SPY", "EFA", "EEM", "IEF", "TLT", "GLD", "DBC", "VNQ", "UUP", "BIL", "SGOV"}))


def check_plan(orders: list, equity: float, positions: dict[str, int], prices: dict[str, float],
               cash: float, limits: RiskLimits = RiskLimits()) -> list[str]:
    """Return a list of violations (empty = OK). `orders` need .symbol .side .qty .limit_price."""
    v: list[str] = []
    if equity <= 0:
        return ["equity is not positive"]
    if len(orders) > limits.max_orders:
        v.append(f"{len(orders)} orders > limit {limits.max_orders}")
    after = dict(positions)
    spend = 0.0
    for o in orders:
        if o.symbol not in limits.allowed_symbols:
            v.append(f"{o.symbol} is not on the allow-list")
        if o.qty <= 0 or int(o.qty) != o.qty:
            v.append(f"{o.symbol}: quantity must be a positive whole number, got {o.qty}")
        if o.side not in ("BUY", "SELL"):
            v.append(f"{o.symbol}: bad side {o.side}")
        ref = prices.get(o.symbol)
        if not ref or ref <= 0:
            v.append(f"{o.symbol}: no valid reference price")
            continue
        if abs(o.limit_price / ref - 1) > limits.max_limit_distance + 1e-12:
            v.append(f"{o.symbol}: limit {o.limit_price} is more than {limits.max_limit_distance:.1%} from {ref}")
        if o.symbol not in CASH_SYMBOLS and o.qty * ref > limits.max_order_fraction * equity:
            v.append(f"{o.symbol}: order value {o.qty * ref:,.0f} > {limits.max_order_fraction:.0%} of equity")
        sign = 1 if o.side == "BUY" else -1
        after[o.symbol] = after.get(o.symbol, 0) + sign * o.qty
        spend += sign * o.qty * o.limit_price
        if after[o.symbol] < 0:
            v.append(f"{o.symbol}: would go short ({after[o.symbol]} shares); shorting is not allowed")
    for sym, q in after.items():
        w = q * prices.get(sym, 0.0) / equity
        if w > limits.max_position_weight + 1e-9 and sym not in CASH_SYMBOLS:
            v.append(f"{sym}: weight {w:.1%} > limit {limits.max_position_weight:.0%}")
    if spend > cash + 1e-6 and spend > 0:
        v.append(f"net cash needed {spend:,.2f} exceeds available cash {cash:,.2f}")
    return v


class DrawdownGuard:
    """Tracks the equity high-water mark in a JSON file and halts trading after a large drawdown.

    Once halted it STAYS halted until a human calls `reset()` - a deliberate friction so the system
    cannot buy back in automatically in the middle of a crash.
    """

    def __init__(self, path: str, limit: float = 0.15):
        self.path, self.limit = Path(path), limit
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"hwm": 0.0, "halted": False}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state))

    def update(self, equity: float) -> bool:
        """Record equity; return True if trading is halted."""
        if equity > self.state["hwm"]:
            self.state["hwm"] = equity
        if self.state["hwm"] > 0 and equity / self.state["hwm"] - 1 <= -self.limit:
            self.state["halted"] = True
        self._save()
        return bool(self.state["halted"])

    def reset(self, equity: float) -> None:
        self.state = {"hwm": equity, "halted": False}
        self._save()
