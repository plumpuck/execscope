"""Command line for the ETF strategy.

  python -m execscope.live.cli fetch    --out data/etf_prices.csv
  python -m execscope.live.cli backtest --prices data/etf_prices.csv
  python -m execscope.live.cli signal   --prices data/etf_prices.csv --equity 8000
  python -m execscope.live.cli paper    --prices data/etf_prices.csv            (dry run)
  python -m execscope.live.cli paper    --prices data/etf_prices.csv --execute
  python -m execscope.live.cli ibkr     --prices data/etf_prices.csv --port 7497   (IBKR PAPER, dry run)

Nothing is ever sent unless --execute is given and you type the confirmation. Real-money ports (7496/4001)
additionally need --i-understand-this-is-real-money AND the environment variable EXECSCOPE_ALLOW_LIVE=1.
"""
import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from execscope.live.broker import PaperBroker
from execscope.live.rebalance import PlanConfig, plan_orders, run_rebalance
from execscope.live.risk import RiskError, RiskLimits
from execscope.portfolio.backtest import BacktestConfig, compare
from execscope.portfolio.data import check_prices, fetch_yfinance, load_prices_csv
from execscope.portfolio.strategy import StrategyConfig, compute_target_weights

LIVE_PHRASE = "I ACCEPT REAL MONEY RISK"


def universe(cfg: StrategyConfig) -> list[str]:
    return [*cfg.risk_assets, cfg.cash]


def ensure_live_allowed(is_paper: bool, flag: bool, env: dict[str, str], typed: str) -> None:
    """Real money needs three separate acts: a flag, an environment variable, and a typed sentence."""
    if is_paper:
        return
    if not flag:
        raise RiskError("this port is a REAL-MONEY account; add --i-understand-this-is-real-money")
    if env.get("EXECSCOPE_ALLOW_LIVE") != "1":
        raise RiskError("set the environment variable EXECSCOPE_ALLOW_LIVE=1 to allow real-money trading")
    if typed.strip() != LIVE_PHRASE:
        raise RiskError(f"confirmation sentence did not match; type exactly: {LIVE_PHRASE}")


def _load(path: str, cfg: StrategyConfig) -> pd.DataFrame:
    df = load_prices_csv(path)
    missing = [t for t in universe(cfg) if t not in df.columns]
    if missing:
        raise SystemExit(f"price file is missing columns: {missing}")
    df = df[universe(cfg)]
    issues = check_prices(df.dropna(how="any"))
    for i in issues:
        print(f"DATA WARNING [{i.kind}] {i.ticker}: {i.detail}")
    return df.dropna(how="any")


def _pct(x: float) -> str:
    return f"{x:+.1%}" if x == x else "n/a"


def cmd_fetch(a, cfg):
    df = fetch_yfinance(universe(cfg), a.start)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out)
    print(f"saved {len(df)} rows {df.index.min().date()} -> {df.index.max().date()} to {a.out}")
    for t in universe(cfg):
        print(f"  {t}: first price {df[t].first_valid_index().date()}")


def cmd_backtest(a, cfg):
    df = _load(a.prices, cfg)
    out = compare(df, cfg, BacktestConfig(capital=a.capital, cost_bps=a.cost_bps, min_fee=a.min_fee))
    print(f"period: {df.index[cfg.min_history].date()} -> {df.index[-1].date()}  (costs: {a.cost_bps} bp + min fee ${a.min_fee})")
    print(f"{'':>14}{'CAGR':>9}{'vol':>8}{'Sharpe':>8}{'maxDD':>9}{'worst mo':>10}{'turnover/yr':>13}")
    for k, p in out["performance"].items():
        print(f"{k:>14}{_pct(p['cagr']):>9}{p['vol']:>8.1%}{p['sharpe_rf0']:>8.2f}{p['max_drawdown']:>9.1%}"
              f"{p['worst_month']:>10.1%}{out['turnover_per_year'][k]:>12.1f}x")
    print("\nSharpe difference, strategy minus benchmark (block-bootstrap 95% interval):")
    for k, d in out["sharpe_diff_vs"].items():
        verdict = "interval excludes 0" if d["ci_low"] > 0 or d["ci_high"] < 0 else "interval includes 0: no clear difference"
        print(f"  vs {k:>13}: {d['diff']:+.2f}  [{d['ci_low']:+.2f}, {d['ci_high']:+.2f}]  ({d['months']} months)  {verdict}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    pd.DataFrame({k: r.equity for k, r in out["runs"].items()}).to_csv(Path(a.out) / "equity.csv")
    (Path(a.out) / "backtest.json").write_text(json.dumps(
        {"performance": out["performance"], "sharpe_diff_vs": out["sharpe_diff_vs"], "config": asdict(cfg)}, indent=2))
    print(f"\nsaved {a.out}/equity.csv and backtest.json")
    print("Past results do not predict future results. Read docs/live-trading-guide.md before using real money.")


def _parse_positions(text: str) -> dict[str, int]:
    return {k: int(v) for k, v in (kv.split("=") for kv in text.split(",") if kv)} if text else {}


def cmd_signal(a, cfg):
    df = _load(a.prices, cfg)
    asof = df.index[-1]
    tw = compute_target_weights(df, asof, cfg)
    print(f"signal as of {asof.date()}  (estimated portfolio vol {tw.vol_estimate:.1%}, target {cfg.target_vol:.0%})")
    for t, w in sorted(tw.weights.items(), key=lambda kv: -kv[1]):
        print(f"  {t:>5} {w:6.1%}   {tw.reasons.get(t, 'cash')}")
    prices = {t: float(df[t].iloc[-1]) for t in universe(cfg)}
    pos = _parse_positions(a.positions)
    orders = plan_orders(a.equity, pos, prices, tw.weights, cfg.cash, PlanConfig())
    print(f"\nwhole-share orders for equity ${a.equity:,.0f} (last-close prices, NOT live quotes):")
    for o in orders or []:
        print(f"  {o.side:>4} {o.qty:>4} {o.symbol:<5} limit {o.limit_price}")
    if not orders:
        print("  (none)")


def _confirm_factory(a, is_paper: bool):
    def confirm(text: str) -> bool:
        print("\nORDERS TO SEND:\n" + text)
        if not is_paper:
            return input(f"type exactly '{LIVE_PHRASE}' to send: ").strip() == LIVE_PHRASE
        return input("send these orders? [y/N] ").strip().lower() == "y"
    return confirm


def _run(a, cfg, broker):
    df = _load(a.prices, cfg)
    ensure_live_allowed(broker.is_paper, getattr(a, "i_understand_this_is_real_money", False), dict(os.environ),
                        LIVE_PHRASE if not a.execute else (LIVE_PHRASE if broker.is_paper else _ask_phrase()))
    rep = run_rebalance(broker, df, cfg, PlanConfig(), RiskLimits(), a.state_dir, a.execute,
                        _confirm_factory(a, broker.is_paper), datetime.now(), a.force)
    print(f"equity ${rep.equity:,.2f}   halted: {rep.halted}")
    for n in rep.notes:
        print("  -", n)
    print("target:", {k: round(v, 3) for k, v in rep.target.items() if v > 0})
    for o in rep.orders:
        print(f"  plan: {o.side} {o.qty} {o.symbol} limit {o.limit_price}")
    for r in rep.results:
        print(f"  result: {r.symbol} {r.side} {r.filled}/{r.requested} @ {r.avg_price:.2f} [{r.status}]")
    if not a.execute:
        print("DRY RUN - nothing was sent. Add --execute to send.")


def _ask_phrase() -> str:  # pragma: no cover - interactive
    return input(f"REAL MONEY. type exactly '{LIVE_PHRASE}' to continue: ")


def cmd_paper(a, cfg):
    df = _load(a.prices, cfg)
    last = {t: float(df[t].iloc[-1]) for t in universe(cfg)}
    broker = PaperBroker(str(Path(a.state_dir) / "paper.json"), a.equity, price_source=lambda s: last[s])
    _run(a, cfg, broker)


def cmd_ibkr(a, cfg):  # pragma: no cover - needs a running TWS / IB Gateway
    from execscope.live.broker import IBKRBroker
    broker = IBKRBroker(a.host, a.port, a.client_id, a.account)
    try:
        _run(a, cfg, broker)
    finally:
        broker.disconnect()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch")
    f.add_argument("--out", default="data/etf_prices.csv")
    f.add_argument("--start", default="2006-01-01")

    b = sub.add_parser("backtest")
    b.add_argument("--prices", required=True)
    b.add_argument("--capital", type=float, default=10_000)
    b.add_argument("--cost-bps", type=float, default=5.0)
    b.add_argument("--min-fee", type=float, default=1.0)
    b.add_argument("--out", default="results/etf")

    s = sub.add_parser("signal")
    s.add_argument("--prices", required=True)
    s.add_argument("--equity", type=float, required=True)
    s.add_argument("--positions", default="", help="current holdings, e.g. SPY=3,IEF=10")

    for name in ("paper", "ibkr"):
        r = sub.add_parser(name)
        r.add_argument("--prices", required=True)
        r.add_argument("--execute", action="store_true")
        r.add_argument("--force", action="store_true", help="ignore the month-end window")
        r.add_argument("--state-dir", default="live_state")
        if name == "paper":
            r.add_argument("--equity", type=float, default=10_000, help="starting paper cash (first run only)")
        else:
            r.add_argument("--host", default="127.0.0.1")
            r.add_argument("--port", type=int, default=7497)
            r.add_argument("--client-id", type=int, default=17)
            r.add_argument("--account", default=None)
            r.add_argument("--i-understand-this-is-real-money", action="store_true")
    a = p.parse_args(argv)
    cfg = StrategyConfig()
    {"fetch": cmd_fetch, "backtest": cmd_backtest, "signal": cmd_signal, "paper": cmd_paper, "ibkr": cmd_ibkr}[a.cmd](a, cfg)


if __name__ == "__main__":
    main()
