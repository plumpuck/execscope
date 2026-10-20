"""One entry point for the named experiments.

  python -W ignore -m execscope.experiments.cli e1 --data synthetic:0
  python -W ignore -m execscope.experiments.cli e2 --data path/to/bars.csv --instrument BTCUSDT
  python -W ignore -m execscope.experiments.cli e3 --data ...
  python -W ignore -m execscope.experiments.cli e4 --trades path/to/BTCUSDT-aggTrades-2024-01-02.zip
  python -W ignore -m execscope.experiments.cli e5 --data ...

e1  algorithms vs one-shot on many parent orders (paired, with intervals)
e2  does the simulated-exchange setting (slippage, latency, liquidity use, intrabar order) move the cost?
e3  does the default fill model understate large-order cost? (vs depth-walking reference and sqrt law)
e4  what do 1-minute bars hide? (bar VWAP and arrival vs the trade tape)
e5  robustness: does the algorithm ranking survive other sizes, horizons and sides?
All results are written under --out as JSON (plus rows.csv for e1).
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from execscope.experiments.harness import (
    ExperimentConfig,
    choose_starts,
    load_data,
    run_experiment,
    save,
)
from execscope.experiments.sweeps import cost_shift_table, run_variants

E2_VARIANTS: dict[str, dict] = {
    "latency_1s": {"venue": {"latency_ms": 1_000}},
    "latency_30s": {"venue": {"latency_ms": 30_000}},
    "latency_60s": {"venue": {"latency_ms": 60_000}},
    "slip_25pct": {"venue": {"prob_slippage": 0.25}},
    "slip_100pct": {"venue": {"prob_slippage": 1.0}},
    "liquidity_consumption": {"venue": {"liquidity_consumption": True}},
    "adaptive_high_low": {"venue": {"bar_adaptive_high_low": True}},
}


def _base(args: argparse.Namespace, name: str) -> ExperimentConfig:
    return ExperimentConfig(name=name, data=args.data, instrument=args.instrument, qty=args.qty,
                            horizon_bars=args.horizon, n_parents=args.parents, seed=args.seed,
                            n_boot=args.boot, algos=[{"name": "oneshot"}, {"name": "twap"}])


def _dump(out: Path, name: str, obj) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    return p


def cmd_e1(args, out):
    cfg = replace(_base(args, "e1"), algos=ExperimentConfig(name="x").algos)
    table, summary, man = run_experiment(cfg)
    print("saved", save(cfg, table, summary, man, str(out)))


def cmd_e2(args, out):
    res = run_variants(_base(args, "e2"), E2_VARIANTS)
    tables = {a: cost_shift_table(res, a) for a in ("oneshot", "twap")}
    print("saved", _dump(out, "e2", {"summaries": res, "shift_tables": tables}))
    for a, t in tables.items():
        print(f"-- {a}: mean cost vs arrival (bp)")
        for r in t:
            print(f"{r['variant']:>24}  {r['mean']:+8.3f}  shift {r['shift_vs_default']:+8.3f}")


def cmd_e3(args, out):
    from execscope.experiments.fidelity import FidelityConfig, run_fidelity, summarise_fidelity
    df, _ = load_data(_base(args, "e3"))
    starts = choose_starts(len(df), args.horizon, args.parents, args.seed, warmup=min(1440, len(df) // 4))
    cfg = FidelityConfig(instrument=args.instrument, n_boot=args.boot, seed=args.seed)
    table = run_fidelity(df, starts, args.horizon, cfg)
    summary = summarise_fidelity(table, cfg)
    print("saved", _dump(out, "e3", {"config": cfg.__dict__, "summary": summary}))
    for q, e in summary.items():
        u = e["understatement_vs_refsim_bps"]
        print(f"size {q:>5}: nautilus {e['nautilus_bps']['mean']:.4f} bp, refsim {e['refsim_bps']['mean']:.4f} bp, "
              f"understatement {u['mean']:.4f} bp [{u['ci_low']:.4f}, {u['ci_high']:.4f}]")


def cmd_e4(args, out):
    from execscope.data.binance import read_binance
    from execscope.experiments.granularity import granularity_bias
    trades = read_binance(args.trades, "aggTrades")
    first, last = trades.index.min().ceil("min"), trades.index.max().floor("min") - pd.Timedelta(minutes=args.horizon)
    grid = pd.date_range(first, last, freq=f"{args.horizon}min")
    pick = pd.Series(grid).sample(n=min(args.parents, len(grid)), random_state=args.seed).sort_values()
    res = granularity_bias(trades, list(pick), args.horizon)
    summary = {c: {"mean": float(res[c].mean()), "median": float(res[c].median()),
                   "p95_abs": float(res[c].abs().quantile(0.95))} for c in res.columns if c != "start"}
    print("saved", _dump(out, "e4", {"n": len(res), "summary": summary}))
    for c, s in summary.items():
        print(f"{c:>32}: mean {s['mean']:+.3f}  median {s['median']:+.3f}  95th pct |x| {s['p95_abs']:.3f}")


def cmd_e5(args, out):
    variants: dict[str, dict] = {f"qty_x{m}": {"qty": args.qty * m} for m in (2, 4)}
    variants |= {f"horizon_{h}": {"horizon_bars": h} for h in (args.horizon // 2, args.horizon * 2)}
    variants["side_SELL"] = {"side": "SELL"}
    res = run_variants(_base(args, "e5"), variants)
    print("saved", _dump(out, "e5", {"summaries": res}))
    for label, r in res.items():
        d = r["paired_vs_baseline"].get("twap", {}).get("vs_vwap_bps")
        if d:
            print(f"{label:>14}: twap - oneshot vs VWAP {d['mean_diff']:+.3f} bp [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}]")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("experiment", choices=["e1", "e2", "e3", "e4", "e5"])
    p.add_argument("--data", default="synthetic:0")
    p.add_argument("--trades", help="Binance aggTrades CSV/zip (e4)")
    p.add_argument("--instrument", default="BTCUSDT", choices=["6EH4", "BTCUSDT"])
    p.add_argument("--qty", type=int, default=60)
    p.add_argument("--horizon", type=int, default=30)
    p.add_argument("--parents", type=int, default=40)
    p.add_argument("--boot", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="results")
    a = p.parse_args(argv)
    {"e1": cmd_e1, "e2": cmd_e2, "e3": cmd_e3, "e4": cmd_e4, "e5": cmd_e5}[a.experiment](a, Path(a.out))


if __name__ == "__main__":
    main()
