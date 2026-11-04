import hashlib
import io
import urllib.error
from datetime import date

import pytest

from execscope.data import download
from execscope.data.download import daily_dates, download_file, download_range, file_url, main

URL = file_url("klines", "BTCUSDT", date(2024, 1, 2))
BODY = b"zip bytes " * 20_000


class FakeNet:
    """Stands in for urllib: `steps` scripts what each request for a zip does, then it serves `BODY`."""

    def __init__(self, steps=(), checksum=None):
        self.steps = list(steps)
        self.checksum = checksum or hashlib.sha256(BODY).hexdigest()
        self.zip_requests = 0

    def urlopen(self, url, timeout=None):
        if url.endswith(".CHECKSUM"):
            return self._response(f"{self.checksum}  file.zip\n".encode("ascii"))
        self.zip_requests += 1
        step = self.steps.pop(0) if self.steps else BODY
        if isinstance(step, Exception):
            raise step
        return self._response(step)

    @staticmethod
    def _response(body):
        resp = io.BytesIO(body)
        resp.headers = {"Content-Length": str(len(body))}
        return resp


@pytest.fixture
def net(monkeypatch):
    def install(*args, **kwargs):
        fake = FakeNet(*args, **kwargs)
        monkeypatch.setattr(download.urllib.request, "urlopen", fake.urlopen)
        return fake
    return install


def _http_error(code):
    return urllib.error.HTTPError(URL, code, "error", None, None)


def test_urls_match_the_binance_archive_layout():
    assert file_url("klines", "BTCUSDT", date(2024, 1, 2)) == \
        "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-02.zip"
    assert file_url("aggTrades", "ETHUSDT", date(2024, 1, 2)) == \
        "https://data.binance.vision/data/spot/daily/aggTrades/ETHUSDT/ETHUSDT-aggTrades-2024-01-02.zip"
    with pytest.raises(ValueError):
        file_url("orderbook", "BTCUSDT", date(2024, 1, 2))


def test_date_range_is_inclusive_and_rejects_reversed_dates():
    assert daily_dates(date(2024, 2, 28), date(2024, 3, 1)) == [date(2024, 2, 28), date(2024, 2, 29), date(2024, 3, 1)]
    with pytest.raises(ValueError):
        daily_dates(date(2024, 1, 2), date(2024, 1, 1))


def test_download_writes_the_file_and_leaves_no_partial(tmp_path, net):
    net()
    path, new = download_file(URL, tmp_path / "raw", progress=False)
    assert new and path.name == "BTCUSDT-1m-2024-01-02.zip" and path.read_bytes() == BODY
    assert [p.name for p in path.parent.iterdir()] == [path.name]


def test_existing_file_is_skipped_without_touching_the_network(tmp_path, net):
    fake = net()
    (tmp_path / "BTCUSDT-1m-2024-01-02.zip").write_bytes(b"already here")
    path, new = download_file(URL, tmp_path, progress=False)
    assert not new and path.read_bytes() == b"already here" and fake.zip_requests == 0


def test_transient_failures_are_retried_with_backoff(tmp_path, net):
    fake = net(steps=[urllib.error.URLError("reset"), _http_error(503)])
    waits = []
    path, _ = download_file(URL, tmp_path, progress=False, sleep=waits.append)
    assert path.read_bytes() == BODY and fake.zip_requests == 3 and waits == [1.0, 2.0]


def test_gives_up_after_the_retry_limit_and_keeps_no_file(tmp_path, net):
    fake = net(steps=[urllib.error.URLError("down")] * 3)
    with pytest.raises(ConnectionError, match="after 3 attempts"):
        download_file(URL, tmp_path, retries=3, progress=False, sleep=lambda _: None)
    assert fake.zip_requests == 3 and list(tmp_path.iterdir()) == []


def test_missing_date_is_not_retried(tmp_path, net):
    fake = net(steps=[_http_error(404)])
    with pytest.raises(FileNotFoundError, match="not published"):
        download_file(URL, tmp_path, progress=False, sleep=lambda _: pytest.fail("should not retry"))
    assert fake.zip_requests == 1


def test_refused_request_is_not_retried(tmp_path, net):
    fake = net(steps=[_http_error(403)])
    with pytest.raises(RuntimeError, match="HTTP 403"):
        download_file(URL, tmp_path, progress=False, sleep=lambda _: pytest.fail("should not retry"))
    assert fake.zip_requests == 1


def test_corrupt_download_never_gets_the_final_name(tmp_path, net):
    fake = net(checksum="0" * 64)
    with pytest.raises(ConnectionError, match="sha256"):
        download_file(URL, tmp_path, retries=2, progress=False, sleep=lambda _: None)
    assert fake.zip_requests == 2 and list(tmp_path.iterdir()) == []


def test_range_resumes_where_it_stopped(tmp_path, net):
    fake = net()
    (tmp_path / "BTCUSDT-1m-2024-01-02.zip").write_bytes(BODY)
    paths = download_range("klines", "BTCUSDT", date(2024, 1, 2), date(2024, 1, 4), out_dir=tmp_path, progress=False)
    assert [p.name[-14:] for p in paths] == ["2024-01-02.zip", "2024-01-03.zip", "2024-01-04.zip"]
    assert fake.zip_requests == 2


def test_cli_reports_an_unreachable_site_instead_of_a_traceback(tmp_path, net, monkeypatch):
    monkeypatch.setattr(download.time, "sleep", lambda _: None)
    net(steps=[urllib.error.URLError("blocked")] * 2)
    with pytest.raises(SystemExit, match="download failed"):
        main(["klines", "BTCUSDT", "2024-01-02", "2024-01-02", "--out-dir", str(tmp_path), "--retries", "2"])
