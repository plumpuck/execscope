"""Download daily Binance spot data zips from https://data.binance.vision into data/raw/.

    python -m execscope.data.download klines BTCUSDT 2024-01-02 2024-01-08
    python -m execscope.data.download aggTrades BTCUSDT 2024-01-02 2024-01-08

Dates are inclusive and UTC. Files already on disk are skipped. Each new file is checked against the
SHA-256 that Binance publishes next to it, and only appears under its final name once that check passes,
so an interrupted download never looks finished. Binance = crypto, not futures-market data.
"""
import argparse
import hashlib
import http.client
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/spot/daily"
KINDS = ("klines", "aggTrades")
CHUNK_BYTES = 64 * 1024
TIMEOUT_SECONDS = 30


class ChecksumError(ValueError):
    """The downloaded bytes do not match the SHA-256 that Binance published."""


def daily_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def file_url(kind: str, symbol: str, day: date, interval: str = "1m") -> str:
    if kind == "klines":
        return f"{BASE_URL}/klines/{symbol}/{interval}/{symbol}-{interval}-{day.isoformat()}.zip"
    if kind == "aggTrades":
        return f"{BASE_URL}/aggTrades/{symbol}/{symbol}-aggTrades-{day.isoformat()}.zip"
    raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")


def _with_retries(fn: Callable[[], None], url: str, retries: int, sleep: Callable[[float], None]) -> None:
    """Retry network failures and bad checksums with exponential backoff; a 404 will not fix itself."""
    if retries < 1:
        raise ValueError("retries must be >= 1")
    last: Exception | None = None
    for attempt in range(retries):
        try:
            fn()
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(f"{url} does not exist: check the symbol, or Binance has not published that date yet") from e
            if e.code < 500 and e.code != 429:
                raise RuntimeError(f"{url} was refused with HTTP {e.code}") from e
            last = e
        except (OSError, http.client.HTTPException, ChecksumError) as e:
            last = e
        if attempt < retries - 1:
            sleep(2.0 ** attempt)
    raise ConnectionError(f"could not download {url} after {retries} attempts: {last}") from last


def _expected_sha256(url: str) -> str:
    """A .CHECKSUM file holds one line: '<sha256>  <file name>'."""
    with urllib.request.urlopen(url + ".CHECKSUM", timeout=TIMEOUT_SECONDS) as resp:
        return resp.read().decode("ascii").split()[0].lower()


def _fetch(url: str, part: Path, progress: bool) -> None:
    expected = _expected_sha256(url)
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp, part.open("wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        while chunk := resp.read(CHUNK_BYTES):
            out.write(chunk)
            digest.update(chunk)
            got += len(chunk)
            if progress:
                print(f"\r{part.stem}: {got / 1e6:.2f} / {total / 1e6:.2f} MB", end="", file=sys.stderr)
    if progress:
        print(file=sys.stderr)
    if digest.hexdigest() != expected:
        raise ChecksumError(f"{part.stem}: sha256 {digest.hexdigest()} != published {expected}")


def download_file(url: str, out_dir: Path, retries: int = 4, progress: bool = True,
                  sleep: Callable[[float], None] = time.sleep) -> tuple[Path, bool]:
    """Return (path, True if newly downloaded). The file only gets its final name once verified."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / url.rsplit("/", 1)[-1]
    if path.exists():
        return path, False
    part = path.with_name(path.name + ".part")
    try:
        _with_retries(lambda: _fetch(url, part, progress), url, retries, sleep)
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)
    return path, True


def download_range(kind: str, symbol: str, start: date, end: date, interval: str = "1m", out_dir: Path = Path("data/raw"),
                   retries: int = 4, progress: bool = True, sleep: Callable[[float], None] = time.sleep) -> list[Path]:
    paths = []
    for day in daily_dates(start, end):
        path, new = download_file(file_url(kind, symbol, day, interval), out_dir, retries, progress, sleep)
        print(f"{'downloaded' if new else 'already have'} {path}")
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=KINDS)
    p.add_argument("symbol", help="e.g. BTCUSDT")
    p.add_argument("start", type=date.fromisoformat, help="first day, YYYY-MM-DD")
    p.add_argument("end", type=date.fromisoformat, help="last day (inclusive), YYYY-MM-DD")
    p.add_argument("--interval", default="1m", help="klines only")
    p.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    p.add_argument("--retries", type=int, default=4)
    a = p.parse_args(argv)
    try:
        paths = download_range(a.kind, a.symbol, a.start, a.end, a.interval, a.out_dir, a.retries)
    except (ConnectionError, FileNotFoundError, RuntimeError) as e:
        sys.exit(f"download failed: {e}")
    print(f"{len(paths)} files in {a.out_dir}")


if __name__ == "__main__":
    main()
