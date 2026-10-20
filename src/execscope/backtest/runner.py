"""Run one parent order through a NautilusTrader backtest and compute its execution cost.

Usage (from the project root, after `pip install -e .[backtest]`):
    python -m execscope.backtest.runner --data path/to/6EH4.XCME_1min_bars.csv --mode twap
"""
import argparse
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model import TraderId
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from execscope.algos.vwap import interval_vwap
from execscope.backtest.strategies import ExecConfig, ExecStrategy
from execscope.tca.metrics import average_price, cost_usd, slippage_bps
from execscope.tca.shortfall import ShortfallResult, implementation_shortfall, vwap_slippage_bps


@dataclass(frozen=True)
class RunResult:
    mode: str
    side: str
    target_qty: int
    multiplier: float
    fills: list[tuple[float, float]]
    arrival_price: float
    end_price: float
    interval_vwap: float
    n_bars: int


def load_bars_csv(path: str) -> pd.DataFrame:
    """CSV with ';' separator and columns timestamp_utc, open, high, low, close, volume."""
    df = pd.read_csv(path, sep=";", decimal=".", header=0, index_col=False)
    df = df.reindex(columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], format="%Y-%m-%d %H:%M:%S")
    return df.rename(columns={"timestamp_utc": "timestamp"}).set_index("timestamp")


def run_backtest(
    df: pd.DataFrame, mode: str = "twap", side: str = "BUY",
    total_qty: int = 10_000, n_slices: int = 9, window_bars: int | None = None,
) -> RunResult:
    """`window_bars`: bars used for the interval-VWAP benchmark. Default = n_slices, the same
    window for every mode, so one-shot and TWAP are compared against the same benchmark."""
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId("EXECSCOPE-001"),
        logging=LoggingConfig(log_level="ERROR"),
    ))
    try:
        engine.add_venue(
            venue=Venue("XCME"), oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            starting_balances=[Money(1_000_000, USD)], base_currency=USD,
            default_leverage=Decimal(1),
        )
        instrument = TestInstrumentProvider.eurusd_future(
            expiry_year=2024, expiry_month=3, venue_name="XCME",
        )
        engine.add_instrument(instrument)
        bar_type = BarType.from_str(f"{instrument.id}-1-MINUTE-LAST-EXTERNAL")
        engine.add_data(BarDataWrangler(bar_type, instrument).process(df))

        strategy = ExecStrategy(ExecConfig(
            bar_type=str(bar_type), side=side, total_qty=total_qty, mode=mode, n_slices=n_slices,
        ))
        engine.add_strategy(strategy)
        engine.run()

        window = strategy.bar_log[: window_bars or n_slices]
        return RunResult(
            mode=mode, side=side, target_qty=total_qty, multiplier=float(instrument.multiplier),
            fills=list(strategy.fills), arrival_price=strategy.arrival_price,
            end_price=strategy.end_price, interval_vwap=interval_vwap(window),
            n_bars=strategy.bars_seen,
        )
    finally:
        engine.dispose()


def analyse(r: RunResult) -> dict:
    """Execution cost of one run versus the arrival price, the interval VWAP and Perold IS."""
    sf: ShortfallResult = implementation_shortfall(
        r.fills, r.side, r.target_qty, decision_price=r.arrival_price,
        arrival_price=r.arrival_price, end_price=r.end_price, multiplier=r.multiplier,
    )
    avg = average_price(r.fills)
    return {
        "mode": r.mode, "side": r.side, "target_qty": r.target_qty,
        "filled_qty": sf.executed_qty, "n_fills": len(r.fills),
        "avg_fill": avg, "arrival": r.arrival_price,
        "slippage_bps": slippage_bps(r.fills, r.arrival_price, r.side),
        "cost_usd": cost_usd(r.fills, r.arrival_price, r.side, r.multiplier),
        "vwap_slippage_bps": vwap_slippage_bps(avg, r.interval_vwap, r.side),
        "is_total_usd": sf.total, "is_execution_usd": sf.execution,
        "is_opportunity_usd": sf.opportunity,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True)
    p.add_argument("--mode", choices=["twap", "oneshot", "both"], default="both")
    p.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    p.add_argument("--qty", type=int, default=10_000)
    p.add_argument("--slices", type=int, default=9)
    a = p.parse_args()
    df = load_bars_csv(a.data)
    modes = ["oneshot", "twap"] if a.mode == "both" else [a.mode]
    for m in modes:
        res = analyse(run_backtest(df, m, a.side, a.qty, a.slices))
        print(f"--- {m} ---")
        for k, v in res.items():
            print(f"{k:>20}: {v:.6f}" if isinstance(v, float) else f"{k:>20}: {v}")


if __name__ == "__main__":
    main()
