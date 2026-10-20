"""Turn downloaded Binance klines files into the bars CSV that ExecScope reads.

    python -m execscope.data.prepare klines BTCUSDT-1m-2024-01-02.zip BTCUSDT-1m-2024-01-03.zip --out data/btcusdt_1m.csv

Several files are concatenated in time order. The result is checked with the data-quality layer and
any problems are printed (gaps are reported but do not stop the conversion).
"""
import argparse

import pandas as pd

from execscope.data.binance import klines_to_bars, read_binance, write_bars_csv
from execscope.data.quality import check_bars


def prepare_klines(paths: list[str]) -> pd.DataFrame:
    frames = [klines_to_bars(read_binance(p, "klines")) for p in paths]
    bars = pd.concat(frames).sort_index()
    return bars[~bars.index.duplicated(keep="first")]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=["klines"])
    p.add_argument("files", nargs="+")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    bars = prepare_klines(a.files)
    write_bars_csv(bars, a.out)
    print(f"wrote {len(bars)} bars {bars.index.min()} -> {bars.index.max()} to {a.out}")
    issues = check_bars(bars)
    print("data quality: clean" if not issues else "data quality issues:")
    for i in issues:
        print(f"  - {i.kind} x{i.count}: {i.detail}")


if __name__ == "__main__":
    main()
