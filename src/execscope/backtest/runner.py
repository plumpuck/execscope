"""Run one parent order through a NautilusTrader backtest and compute its execution cost.

CLI (from the project root, after `pip install -e ".[backtest]"`):
    python -W ignore -m execscope.backtest.runner --data path/to/bars.csv --algo twap
"""
import argparse
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FillModel, LatencyModel
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model import TraderId
from nautilus_trader.model.currencies import USD, USDT
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from execscope.algos.schedules import volume_profile_schedule
from execscope.algos.twap import twap_schedule
from execscope.algos.vwap import interval_vwap
from execscope.backtest.strategies import ExecConfig, ExecStrategy
from execscope.models.almgren_chriss import ac_schedule
from execscope.tca.benchmarks import slippage_vs
from execscope.tca.metrics import average_price, cost_usd, slippage_bps
from execscope.tca.shortfall import implementation_shortfall

ALGOS = ("oneshot", "twap", "vwap", "pov", "ac")


@dataclass(frozen=True)
class VenueSettings:
    """Simulated-exchange knobs that change fills (swept in experiment E2)."""
    prob_slippage: float = 0.0          # chance a fill slips one extra tick
    latency_ms: float = 0.0             # order-insert delay
    liquidity_consumption: bool = False  # trades/levels consumed by earlier fills
    bar_adaptive_high_low: bool = False  # intrabar high/low ordering heuristic
    seed: int = 1


@dataclass(frozen=True)
class AlgoSpec:
    name: str = "twap"
    slices: int = 9                      # twap / vwap / ac: number of bars used
    pov_rate: float = 0.1                # pov
    kappa_t: float = 2.0                 # ac
    profile: tuple[float, ...] = ()      # vwap: expected volume profile over `slices` bars


@dataclass(frozen=True)
class RunResult:
    algo: str
    side: str
    target_qty: int
    multiplier: float
    fills: list[tuple[float, float]]
    arrival_price: float
    end_price: float
    interval_vwap: float
    window_volume: float
    n_bars: int
    extra: dict = field(default_factory=dict)


def load_bars_csv(path: str) -> pd.DataFrame:
    """CSV with ';' separator and columns timestamp_utc, open, high, low, close, volume."""
    df = pd.read_csv(path, sep=";", decimal=".", header=0, index_col=False)
    df = df.reindex(columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], format="%Y-%m-%d %H:%M:%S")
    return df.rename(columns={"timestamp_utc": "timestamp"}).set_index("timestamp")


def _wrangler_ready(df: pd.DataFrame) -> pd.DataFrame:
    """NautilusTrader's wrangler needs a writable numpy buffer. With pandas >= 3 (copy-on-write) an
    all-float frame hands out a read-only one, so give `volume` its own dtype: integer when the
    volumes are whole numbers, else float32 (relative error ~1e-7, irrelevant for liquidity)."""
    out = df.copy()
    if out.to_numpy().flags.writeable:
        return out
    vol = out["volume"]
    out["volume"] = vol.astype("int64") if (vol % 1 == 0).all() else vol.astype("float32")
    return out


def build_schedule(spec: AlgoSpec, total_qty: int) -> tuple[list[int], float]:
    """(child sizes per bar, pov_rate). A pov algo returns ([], rate)."""
    if spec.name == "oneshot":
        return [total_qty], 0.0
    if spec.name == "twap":
        return twap_schedule(total_qty, spec.slices), 0.0
    if spec.name == "vwap":
        weights = spec.profile or (1.0,) * spec.slices
        if len(weights) != spec.slices:
            raise ValueError("profile length must equal slices")
        return volume_profile_schedule(total_qty, weights), 0.0
    if spec.name == "ac":
        return ac_schedule(total_qty, spec.slices, spec.kappa_t), 0.0
    if spec.name == "pov":
        return [], spec.pov_rate
    raise ValueError(f"unknown algo {spec.name!r}; choose from {ALGOS}")


def _instrument_and_venue(name: str):
    if name == "6EH4":
        inst = TestInstrumentProvider.eurusd_future(expiry_year=2024, expiry_month=3, venue_name="XCME")
        return inst, Venue("XCME"), AccountType.MARGIN, USD, [Money(1_000_000_000, USD)], Decimal(1)
    if name == "BTCUSDT":
        inst = TestInstrumentProvider.btcusdt_binance()
        return inst, inst.id.venue, AccountType.CASH, None, [Money(10_000_000_000, USDT)], None
    raise ValueError("instrument must be '6EH4' or 'BTCUSDT'")


def run_backtest(
    df: pd.DataFrame, spec: AlgoSpec = AlgoSpec(), side: str = "BUY", total_qty: int = 10_000,
    instrument: str = "6EH4", venue: VenueSettings = VenueSettings(), window_bars: int | None = None,
) -> RunResult:
    """Execute one parent order on the bars in `df` (first bar = start). `window_bars` is the bar
    window used for interval VWAP, volume and end price (default: all bars in `df`)."""
    schedule, pov_rate = build_schedule(spec, total_qty)
    inst, venue_id, account, base_ccy, balances, leverage = _instrument_and_venue(instrument)
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId("EXECSCOPE-001"), logging=LoggingConfig(log_level="ERROR"),
    ))
    try:
        engine.add_venue(
            venue=venue_id, oms_type=OmsType.NETTING, account_type=account,
            starting_balances=balances, base_currency=base_ccy, default_leverage=leverage,
            fill_model=FillModel(prob_slippage=venue.prob_slippage, random_seed=venue.seed),
            latency_model=LatencyModel(base_latency_nanos=int(venue.latency_ms * 1_000_000)) if venue.latency_ms > 0 else None,
            liquidity_consumption=venue.liquidity_consumption,
            bar_adaptive_high_low_ordering=venue.bar_adaptive_high_low,
        )
        engine.add_instrument(inst)
        bar_type = BarType.from_str(f"{inst.id}-1-MINUTE-LAST-EXTERNAL")
        engine.add_data(BarDataWrangler(bar_type, inst).process(_wrangler_ready(df)))
        strategy = ExecStrategy(ExecConfig(
            bar_type=str(bar_type), side=side, total_qty=total_qty,
            schedule=tuple(schedule), pov_rate=pov_rate,
        ))
        engine.add_strategy(strategy)
        engine.run()

        n = window_bars or len(strategy.bar_log)
        window = strategy.bar_log[:n]
        return RunResult(
            algo=spec.name, side=side, target_qty=total_qty, multiplier=float(inst.multiplier),
            fills=list(strategy.fills), arrival_price=strategy.arrival_price,
            end_price=window and df["close"].iloc[min(n, len(df)) - 1] or strategy.end_price,
            interval_vwap=interval_vwap(window), window_volume=sum(v for _, v in window),
            n_bars=strategy.bars_seen, extra={"submitted": strategy.submitted},
        )
    finally:
        engine.dispose()


def analyse(r: RunResult) -> dict:
    """Execution cost of one run versus arrival, interval VWAP, close, and Perold IS."""
    filled = sum(q for q, _ in r.fills)
    base = {"algo": r.algo, "side": r.side, "target_qty": r.target_qty, "filled_qty": filled,
            "n_fills": len(r.fills), "arrival": r.arrival_price, "window_vwap": r.interval_vwap,
            "window_volume": r.window_volume}
    sf = implementation_shortfall(
        r.fills, r.side, r.target_qty, decision_price=r.arrival_price, arrival_price=r.arrival_price,
        end_price=r.end_price, multiplier=r.multiplier,
    )
    if not r.fills:
        return {**base, "avg_fill": float("nan"), "vs_arrival_bps": float("nan"),
                "vs_vwap_bps": float("nan"), "vs_close_bps": float("nan"), "cost_usd": 0.0,
                "is_total_usd": sf.total, "is_execution_usd": 0.0, "is_opportunity_usd": sf.opportunity,
                "is_total_bps": sf.total_bps, "participation": 0.0}
    avg = average_price(r.fills)
    return {
        **base, "avg_fill": avg,
        "vs_arrival_bps": slippage_bps(r.fills, r.arrival_price, r.side),
        "vs_vwap_bps": slippage_vs(avg, r.interval_vwap, r.side),
        "vs_close_bps": slippage_vs(avg, r.end_price, r.side),
        "cost_usd": cost_usd(r.fills, r.arrival_price, r.side, r.multiplier),
        "is_total_usd": sf.total, "is_execution_usd": sf.execution,
        "is_opportunity_usd": sf.opportunity, "is_total_bps": sf.total_bps,
        "participation": filled / r.window_volume if r.window_volume > 0 else float("nan"),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True)
    p.add_argument("--algo", choices=[*ALGOS, "all"], default="all")
    p.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    p.add_argument("--qty", type=int, default=10_000)
    p.add_argument("--slices", type=int, default=9)
    p.add_argument("--instrument", default="6EH4", choices=["6EH4", "BTCUSDT"])
    a = p.parse_args()
    df = load_bars_csv(a.data)
    algos = ["oneshot", "twap", "vwap", "pov", "ac"] if a.algo == "all" else [a.algo]
    for name in algos:
        res = analyse(run_backtest(df, AlgoSpec(name, slices=a.slices), a.side, a.qty, a.instrument,
                                   window_bars=a.slices))
        print(f"--- {name} ---")
        for k, v in res.items():
            print(f"{k:>20}: {v:.6f}" if isinstance(v, float) else f"{k:>20}: {v}")


if __name__ == "__main__":
    main()
