"""Readers for Binance public market data (https://data.binance.vision) -> pandas.

Supported file kinds (CSV or the .zip that Binance publishes, one CSV inside):
  klines     open_time, open, high, low, close, volume, close_time, quote_volume, count,
             taker_buy_volume, taker_buy_quote_volume, ignore
  aggTrades  agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time,
             is_buyer_maker [, is_best_match]
  bookTicker update_id, best_bid_price, best_bid_qty, best_ask_price, best_ask_qty,
             transaction_time, event_time

Binance files differ by market (spot has no header row, futures do) and spot timestamps switched from
milliseconds to microseconds in 2025, so both are handled. The column layouts above follow Binance's
published documentation; ALWAYS run `describe()` on the first file you download and eyeball it before
trusting an experiment.
"""
import glob

import pandas as pd

LAYOUTS = {
    "klines": ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
               "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"],
    "aggTrades": ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
                  "transact_time", "is_buyer_maker", "is_best_match"],
    "bookTicker": ["update_id", "best_bid_price", "best_bid_qty", "best_ask_price", "best_ask_qty",
                   "transaction_time", "event_time"],
}
TIME_COLUMN = {"klines": "open_time", "aggTrades": "transact_time", "bookTicker": "transaction_time"}


def _to_datetime(s: pd.Series) -> pd.Series:
    """Epoch integers in ms (13 digits) or us (16 digits) -> naive UTC timestamps."""
    first = int(s.iloc[0])
    unit = "us" if first >= 10**15 else "ms"
    if first < 10**11:
        raise ValueError(f"timestamp {first} does not look like epoch milliseconds or microseconds")
    return pd.to_datetime(s.astype("int64"), unit=unit)


def expand_paths(patterns: list[str]) -> list[str]:
    """Expand wildcards here because PowerShell does not. A pattern that matches nothing is kept as given."""
    return [match for p in patterns for match in sorted(glob.glob(p)) or [p]]


def _is_header(first_cell: str) -> bool:
    """A header row starts with a non-numeric token such as "open_time" or "agg_trade_id"."""
    return not first_cell.lstrip("-").replace(".", "", 1).isdigit()


def read_columns(path: str, kind: str, columns: tuple[str, ...]) -> pd.DataFrame:
    """Read only the time column and the numeric `columns`, as numbers. A day of aggTrades is over 100 MB of
    text, so this uses a small fraction of the memory that `read_binance` needs."""
    time_col = TIME_COLUMN[kind]
    first = pd.read_csv(path, header=None, dtype=str, nrows=1)
    df = pd.read_csv(path, header=None, names=LAYOUTS[kind][: first.shape[1]], usecols=[time_col, *columns],
                     skiprows=int(_is_header(first.iloc[0, 0])), dtype={time_col: "int64", **dict.fromkeys(columns, "float64")})
    df[time_col] = _to_datetime(df[time_col])
    return df.set_index(time_col).sort_index()


def read_binance(path: str, kind: str) -> pd.DataFrame:
    if kind not in LAYOUTS:
        raise ValueError(f"kind must be one of {sorted(LAYOUTS)}")
    raw = pd.read_csv(path, header=None, dtype=str)
    if _is_header(raw.iloc[0, 0]):
        raw = raw.iloc[1:].reset_index(drop=True)
    names = LAYOUTS[kind][: raw.shape[1]]
    if raw.shape[1] < len(names):
        raise ValueError(f"{kind} file has {raw.shape[1]} columns, expected at least {len(LAYOUTS[kind]) - 1}")
    raw.columns = names
    df = raw.copy()
    df[TIME_COLUMN[kind]] = _to_datetime(df[TIME_COLUMN[kind]])
    for c in df.columns:
        if c == TIME_COLUMN[kind] or c in ("is_buyer_maker", "is_best_match"):
            continue
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "is_buyer_maker" in df.columns:
        df["is_buyer_maker"] = df["is_buyer_maker"].astype(str).str.lower().isin(["true", "1"])
    return df.set_index(TIME_COLUMN[kind]).sort_index()


def klines_to_bars(klines: pd.DataFrame) -> pd.DataFrame:
    """Binance klines -> the bars layout used everywhere in ExecScope."""
    bars = klines[["open", "high", "low", "close", "volume"]].copy()
    bars.index.name = "timestamp"
    return bars


def trades_to_bars(trades: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Aggregate a trade tape into OHLCV bars. Empty minutes are dropped (no trades, no bar)."""
    g = trades["price"].resample(freq)
    bars = pd.DataFrame({"open": g.first(), "high": g.max(), "low": g.min(), "close": g.last(),
                         "volume": trades["quantity"].resample(freq).sum()}).dropna(subset=["open"])
    bars.index.name = "timestamp"
    return bars


def write_bars_csv(bars: pd.DataFrame, path: str) -> None:
    """Write the ';'-separated layout read by `execscope.backtest.runner.load_bars_csv`."""
    out = bars.reset_index().rename(columns={bars.index.name or "index": "timestamp_utc"})
    out["timestamp_utc"] = out["timestamp_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(path, sep=";", index=False)


def describe(df: pd.DataFrame) -> str:
    return f"{len(df)} rows, {df.index.min()} -> {df.index.max()}\n{df.head(3).to_string()}"
