"""Collect public Binance spot L2 snapshots, then replay static size/cost curves offline.

python -m execscope.experiments.depth collect --out data/raw/depth.jsonl
python -m execscope.experiments.depth analyse --input data/raw/depth.jsonl --out results/depth

No API keys, orders or account connections. Capture times are local UTC request bounds:
the REST depth response has an update ID, NOT an exchange timestamp. Every response is retained.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from execscope.refsim.snapshot import parse_snapshot, sweep_snapshot

BASE = "https://data-api.binance.vision/api/v3/depth"
LIMITATIONS = [
    "Static displayed-liquidity sweep only; not realised execution or permanent market impact.",
    "Current snapshots cannot calibrate historical October/November bar windows retroactively.",
    "No fees, latency, cancellations, hidden liquidity, resilience or permanent impact fitted.",
    "Finite depth: partial fills are censored; no full-order cost is estimated beyond the book.",
    "Adjacent snapshots are dependent; descriptive summaries only, no iid confidence intervals.",
    "Timestamps are local UTC request bounds, not exchange event timestamps.",
]


def collect(out: Path, symbol: str, samples: int, interval: float, limit: int) -> None:
    if not symbol.isalnum() or not symbol.isascii():
        raise ValueError("symbol must be ASCII alphanumeric")
    if not 1 <= samples <= 120 or not math.isfinite(interval) or interval < 5:
        raise ValueError("need 1..120 samples and a finite interval >= 5 seconds")
    if limit not in (5, 10, 20, 50, 100, 500, 1000, 5000):
        raise ValueError("unsupported depth limit")
    url = BASE + "?" + urllib.parse.urlencode({"symbol": symbol.upper(), "limit": limit})
    out.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create: interrupted files remain valid prefixes; existing captures are never overwritten.
    with out.open("x", encoding="utf-8") as f:
        for i in range(samples):
            started = datetime.now(UTC).isoformat()
            with urllib.request.urlopen(url, timeout=20) as response:
                raw = response.read()
            received = datetime.now(UTC).isoformat()
            payload = json.loads(raw)
            parse_snapshot(payload)
            record = {"schema": 1, "symbol": symbol.upper(), "url": url, "requested_limit": limit,
                      "request_started_utc": started, "received_utc": received,
                      "response_sha256": hashlib.sha256(raw).hexdigest(),
                      "response_text": raw.decode("utf-8")}
            f.write(json.dumps(record) + "\n")
            f.flush()
            print(f"captured {i + 1}/{samples}: update {payload['lastUpdateId']}", flush=True)
            if i + 1 < samples:
                time.sleep(interval)


def analyse(source: Path, out: Path, sizes: list[float]) -> dict:
    if not sizes or any(not math.isfinite(q) or q <= 0 for q in sizes) or len(set(sizes)) != len(sizes):
        raise ValueError("sizes must be distinct positive finite quantities")
    raw = source.read_bytes()
    rows, profiles, seen = [], [], set()
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError("capture is empty")
    symbols = {r["symbol"] for r in records}
    if len(symbols) != 1:
        raise ValueError("cannot mix symbols")
    for i, record in enumerate(records):
        response_text = record["response_text"]
        if hashlib.sha256(response_text.encode("utf-8")).hexdigest() != record["response_sha256"]:
            raise ValueError("response checksum mismatch")
        book = parse_snapshot(json.loads(response_text))
        if book.update_id in seen:
            continue  # stale duplicate observations must not increase the sample count
        seen.add(book.update_id)
        for side, levels in (("BUY", book.asks), ("SELL", book.bids)):
            cumulative = 0.0
            for k, (price, qty) in enumerate(levels):
                cumulative += qty
                profiles.append({"snapshot": i, "update_id": book.update_id, "side": side,
                                 "level": k + 1, "price": price, "qty": qty, "cumulative_qty": cumulative})
            for q in sizes:
                rows.append({"snapshot": i, "update_id": book.update_id,
                             "received_utc": record["received_utc"], **sweep_snapshot(book, side, q)})
    summary = []
    for side in ("BUY", "SELL"):
        for q in sizes:
            group = [r for r in rows if r["side"] == side and r["qty"] == q]
            costs = [r["full_order_cost_vs_mid_bps"] for r in group if not r["depth_exhausted"]]
            summary.append({"side": side, "qty": q, "n": len(group), "n_complete": len(costs),
                            "min_fill_rate": min(r["fill_rate"] for r in group),
                            "mean_full_cost_bps": statistics.mean(costs) if costs else None,
                            "min_full_cost_bps": min(costs) if costs else None,
                            "max_full_cost_bps": max(costs) if costs else None})
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    report = {"symbol": next(iter(symbols)), "capture_records": len(records), "unique_updates": len(seen),
              "first_request_utc": records[0]["request_started_utc"], "last_received_utc": records[-1]["received_utc"],
              "input_path": str(source.resolve()), "input_sha256": hashlib.sha256(raw).hexdigest(),
              "git_commit": commit, "working_tree_dirty": dirty, "sizes": sizes,
              "source_sha256": {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (Path(__file__), Path(__file__).parents[1] / "refsim" / "snapshot.py")},
              "calibration": "Observed per-snapshot price/quantity ladders; no parametric depth extrapolation.",
              "limitations": LIMITATIONS, "summary": summary}
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (("sweeps.csv", rows), ("depth_profiles.csv", profiles)):
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (out / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--symbol", default="BTCUSDT")
    c.add_argument("--samples", type=int, default=6)
    c.add_argument("--interval", type=float, default=5)
    c.add_argument("--limit", type=int, default=1000)
    a = sub.add_parser("analyse")
    a.add_argument("--input", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--sizes", type=float, nargs="+", default=[1, 5, 20, 60, 120, 240])
    args = p.parse_args(argv)
    if args.command == "collect":
        collect(args.out, args.symbol, args.samples, args.interval, args.limit)
    else:
        report = analyse(args.input, args.out, args.sizes)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
