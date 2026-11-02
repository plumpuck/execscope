"""Daily price data for the ETF strategy: load, fetch, check.

Prices must be ADJUSTED closes (dividends reinvested), one column per ticker, DatetimeIndex.
Bad data silently ruins a backtest, so `check_prices` is called before every run.
"""
from dataclasses import dataclass

import pandas as pd


def load_prices_csv(path: str) -> pd.DataFrame:
    """Wide CSV: first column = date, one column per ticker (adjusted close)."""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.sort_index()


def fetch_yfinance(tickers: list[str], start: str = "2005-01-01") -> pd.DataFrame:
    """Download adjusted closes with the optional `yfinance` package (pip install yfinance).

    Yahoo data is free and convenient but unofficial; compare against IBKR history before real money.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("pip install yfinance") from exc
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)
    close = raw["Close"] if "Close" in raw else raw
    return close[tickers].dropna(how="all").sort_index()


@dataclass(frozen=True)
class PriceIssue:
    kind: str
    ticker: str
    detail: str


def check_prices(df: pd.DataFrame, max_daily_move: float = 0.25, max_stale_days: int = 5) -> list[PriceIssue]:
    issues: list[PriceIssue] = []
    if not df.index.is_monotonic_increasing:
        issues.append(PriceIssue("unsorted", "*", "dates are not increasing"))
    if df.index.duplicated().any():
        issues.append(PriceIssue("duplicate_dates", "*", f"{int(df.index.duplicated().sum())} repeated dates"))
    for t in df.columns:
        s = df[t].dropna()
        if s.empty:
            issues.append(PriceIssue("empty", t, "no prices"))
            continue
        if (s <= 0).any():
            issues.append(PriceIssue("non_positive", t, "price <= 0"))
        jumps = s.pct_change().abs() > max_daily_move
        if jumps.any():
            issues.append(PriceIssue("big_move", t, f"{int(jumps.sum())} daily moves > {max_daily_move:.0%} (split not adjusted?)"))
        run = (s.diff() == 0).astype(int)
        longest = run.groupby((run == 0).cumsum()).sum().max()
        if longest >= max_stale_days:
            issues.append(PriceIssue("stale", t, f"price unchanged for {int(longest)} days in a row"))
    return issues
