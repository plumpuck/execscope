"""Data-quality checks for OHLCV bar data. Run these BEFORE trusting any experiment."""
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Issue:
    kind: str
    count: int
    detail: str


def check_bars(
    df: pd.DataFrame, freq: str = "1min", outlier_mads: float = 12.0, min_outlier_move: float = 0.005,
) -> list[Issue]:
    """Return a list of issues (empty = clean). `df` has a DatetimeIndex and open/high/low/close/volume.

    A return is an outlier only if it is both > `outlier_mads` robust sigmas (MAD-based) AND larger than
    `min_outlier_move` (0.5%) in absolute size: tick-sized data has a tiny MAD, so the size floor avoids
    flagging ordinary one-tick moves.
    """
    issues: list[Issue] = []
    if df.empty:
        return [Issue("empty", 0, "no rows")]
    idx = df.index
    if not idx.is_monotonic_increasing:
        issues.append(Issue("unsorted", int((idx[1:] < idx[:-1]).sum()), "timestamps go backwards"))
    dup = int(idx.duplicated().sum())
    if dup:
        issues.append(Issue("duplicate_timestamps", dup, "repeated bar timestamps"))
    step = pd.Timedelta(freq)
    sorted_idx = idx.sort_values().unique()
    gaps = pd.Series(sorted_idx[1:] - sorted_idx[:-1])
    big = gaps[gaps > step]
    if len(big):
        missing = int(((big / step) - 1).sum())
        issues.append(Issue("gaps", len(big), f"{missing} missing bars, longest gap {big.max()}"))
    prices = df[["open", "high", "low", "close"]]
    nonpos = int((prices <= 0).any(axis=1).sum())
    if nonpos:
        issues.append(Issue("non_positive_price", nonpos, "price <= 0"))
    bad_ohlc = int(((df["high"] < df[["open", "close", "low"]].max(axis=1))
                    | (df["low"] > df[["open", "close", "high"]].min(axis=1))).sum())
    if bad_ohlc:
        issues.append(Issue("ohlc_inconsistent", bad_ohlc, "high < max(o,c,l) or low > min(o,c,h)"))
    if (df["volume"] < 0).any():
        issues.append(Issue("negative_volume", int((df["volume"] < 0).sum()), "volume < 0"))
    zero = int((df["volume"] == 0).sum())
    if zero:
        issues.append(Issue("zero_volume", zero, "bars with no volume"))
    ret = df["close"].pct_change().dropna()
    if len(ret) >= 10:
        med = ret.median()
        mad = (ret - med).abs().median()
        if mad > 0:
            dev = (ret - med).abs()
            out = int(((dev > outlier_mads * 1.4826 * mad) & (ret.abs() > min_outlier_move)).sum())
            if out:
                issues.append(Issue("return_outliers", out, f"|return| > {outlier_mads} robust sigmas"))
    return issues


def assert_clean(df: pd.DataFrame, freq: str = "1min", allow: tuple[str, ...] = ()) -> None:
    bad = [i for i in check_bars(df, freq) if i.kind not in allow]
    if bad:
        raise ValueError("data quality problems: " + "; ".join(f"{i.kind} x{i.count} ({i.detail})" for i in bad))
