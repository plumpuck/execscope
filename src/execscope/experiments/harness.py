"""Repeated-parent-order experiments with confidence intervals.

One experiment = many parent orders (random non-overlapping windows of the same data) x several
execution algorithms, each run through NautilusTrader. The same parent orders are used for every
algorithm, so differences are PAIRED (much tighter than comparing two averages).

Run:  python -W ignore -m execscope.experiments.harness configs/e1_sample.json
Outputs (results/<name>/): rows.csv, summary.json, manifest.json
"""
import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from execscope.algos.schedules import build_volume_profile
from execscope.backtest.runner import (
    AlgoSpec, VenueSettings, analyse, load_bars_csv, run_backtest,
)
from execscope.data.quality import assert_clean
from execscope.data.synthetic import synthetic_minute_bars
from execscope.stats.bootstrap import bootstrap_ci, paired_diff_ci, sign_test_p

METRICS = ("vs_vwap_bps", "vs_arrival_bps", "vs_close_bps", "is_total_bps", "cost_usd")


@dataclass
class ExperimentConfig:
    name: str
    data: str = "synthetic:0"            # CSV path, or "synthetic:<seed>"
    instrument: str = "BTCUSDT"
    side: str = "BUY"
    qty: int = 60
    horizon_bars: int = 30
    n_parents: int = 40
    algos: list[dict] = field(default_factory=lambda: [
        {"name": "oneshot"}, {"name": "twap"}, {"name": "vwap"},
        {"name": "pov", "pov_rate": 0.1}, {"name": "ac", "kappa_t": 2.0}])
    venue: dict = field(default_factory=dict)
    seed: int = 0
    baseline: str = "oneshot"
    n_boot: int = 2000
    quality_allow: list[str] = field(default_factory=lambda: ["zero_volume", "gaps"])

    @classmethod
    def from_json(cls, path: str) -> "ExperimentConfig":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def load_data(cfg: ExperimentConfig) -> tuple[pd.DataFrame, str]:
    if cfg.data.startswith("synthetic:"):
        seed = int(cfg.data.split(":")[1])
        return synthetic_minute_bars(seed=seed), f"synthetic:{seed}"
    digest = hashlib.sha256(Path(cfg.data).read_bytes()).hexdigest()
    return load_bars_csv(cfg.data), f"sha256:{digest}"


def profile_before(df: pd.DataFrame, t0: pd.Timestamp, horizon: int, max_days: int = 10) -> list[float] | None:
    """Expected volume profile for the window starting at t0, built ONLY from earlier days at the
    same time of day (no look-ahead). Returns None when there is no usable history."""
    rows = []
    for d in range(1, max_days + 1):
        s = t0 - pd.Timedelta(days=d)
        part = df["volume"].loc[s: s + pd.Timedelta(minutes=horizon - 1)]
        if len(part) == horizon:
            rows.append(part.tolist())
    return build_volume_profile(rows) if rows else None


def choose_starts(n_rows: int, horizon: int, n_parents: int, seed: int, warmup: int) -> list[int]:
    candidates = list(range(warmup, n_rows - horizon, horizon))   # non-overlapping windows
    if len(candidates) < n_parents:
        raise ValueError(f"only {len(candidates)} non-overlapping windows available, need {n_parents}")
    return sorted(random.Random(seed).sample(candidates, n_parents))


def run_experiment(cfg: ExperimentConfig) -> tuple[pd.DataFrame, dict, dict]:
    df, data_id = load_data(cfg)
    assert_clean(df, allow=tuple(cfg.quality_allow))
    venue = VenueSettings(**cfg.venue)
    day_bars = 1440
    starts = choose_starts(len(df), cfg.horizon_bars, cfg.n_parents, cfg.seed, warmup=min(day_bars, len(df) // 4))
    rows = []
    for p, s in enumerate(starts):
        window = df.iloc[s: s + cfg.horizon_bars]
        profile = profile_before(df, window.index[0], cfg.horizon_bars)
        for a in cfg.algos:
            spec = AlgoSpec(
                name=a["name"], slices=a.get("slices", cfg.horizon_bars),
                pov_rate=a.get("pov_rate", 0.1), kappa_t=a.get("kappa_t", 2.0),
                profile=tuple(profile) if (a["name"] == "vwap" and profile) else (),
            )
            r = run_backtest(window, spec, cfg.side, cfg.qty, cfg.instrument, venue, window_bars=cfg.horizon_bars)
            label = a.get("label", a["name"])
            rows.append({"parent": p, "start": str(window.index[0]), **analyse(r), "label": label})
    table = pd.DataFrame(rows)
    return table, summarise(table, cfg), manifest(cfg, data_id)


def summarise(table: pd.DataFrame, cfg: ExperimentConfig) -> dict:
    out: dict = {"algos": {}, "paired_vs_baseline": {}}
    base = table[table["label"] == cfg.baseline].set_index("parent")
    for label, g in table.groupby("label", sort=False):
        g = g.set_index("parent")
        entry = {"n": int(len(g)), "fill_rate": float((g["filled_qty"] / g["target_qty"]).mean())}
        for m in METRICS:
            vals = g[m].dropna().tolist()
            if len(vals) >= 2:
                est, lo, hi = bootstrap_ci(vals, n_boot=cfg.n_boot, seed=cfg.seed)
                entry[m] = {"mean": est, "ci_low": lo, "ci_high": hi}
        out["algos"][label] = entry
        if label != cfg.baseline and not base.empty:
            paired = {}
            for m in METRICS:
                both = pd.concat([g[m], base[m]], axis=1, keys=["a", "b"]).dropna()
                if len(both) >= 2:
                    est, lo, hi = paired_diff_ci(both["a"].tolist(), both["b"].tolist(), n_boot=cfg.n_boot, seed=cfg.seed)
                    paired[m] = {"mean_diff": est, "ci_low": lo, "ci_high": hi,
                                 "sign_test_p": sign_test_p((both["a"] - both["b"]).tolist())}
            out["paired_vs_baseline"][label] = paired
    return out


def manifest(cfg: ExperimentConfig, data_id: str) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                cwd=Path(__file__).parent, timeout=5).stdout.strip() or None
    except Exception:
        commit = None
    import nautilus_trader
    return {"config": asdict(cfg), "data": data_id, "git_commit": commit,
            "python": sys.version.split()[0], "platform": platform.platform(),
            "nautilus_trader": nautilus_trader.__version__}


def save(cfg: ExperimentConfig, table: pd.DataFrame, summary: dict, man: dict, root: str = "results") -> Path:
    out = Path(root) / cfg.name
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "rows.csv", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config")
    p.add_argument("--out", default="results")
    a = p.parse_args()
    cfg = ExperimentConfig.from_json(a.config)
    table, summary, man = run_experiment(cfg)
    out = save(cfg, table, summary, man, a.out)
    print(f"saved to {out}")
    for label, e in summary["algos"].items():
        v = e.get("vs_vwap_bps")
        if v:
            print(f"{label:>10}: vs VWAP {v['mean']:+.3f} bp  [{v['ci_low']:+.3f}, {v['ci_high']:+.3f}]  fill {e['fill_rate']:.2f}")


if __name__ == "__main__":
    main()
