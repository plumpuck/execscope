import hashlib
import json

import pytest

from execscope.experiments.depth import analyse, collect
from execscope.refsim.snapshot import parse_snapshot, sweep_snapshot


def payload():
    return {"lastUpdateId": 10, "bids": [["99", "2"], ["97", "3"]],
            "asks": [["101", "1"], ["104", "2"]]}


def test_observed_prices_spread_and_sides():
    book = parse_snapshot(payload())
    buy = sweep_snapshot(book, "BUY", 2)
    assert buy["average_fill_price"] == 102.5
    assert buy["full_order_cost_vs_mid_bps"] == 250
    assert buy["levels_used"] == 2
    sell = sweep_snapshot(book, "SELL", 3)
    assert sell["average_fill_price"] == pytest.approx(295 / 3)
    assert sell["full_order_cost_vs_mid_bps"] == pytest.approx(166.6666667)


def test_exhausted_book_does_not_invent_fills_or_full_cost():
    r = sweep_snapshot(parse_snapshot(payload()), "BUY", 10)
    assert r["filled_qty"] == 3
    assert r["unfilled_qty"] == 7
    assert r["fill_rate"] == 0.3
    assert r["depth_exhausted"]
    assert r["full_order_cost_vs_mid_bps"] is None


@pytest.mark.parametrize("levels", [[], [[101, 0]], [[101, -1]], [[float("nan"), 1]],
                                   [[101, float("inf")]], [[104, 1], [101, 2]], [[101, 1], [101, 2]]])
def test_invalid_books_rejected(levels):
    p = payload()
    p["asks"] = levels
    with pytest.raises(ValueError):
        parse_snapshot(p)


def test_crossed_book_rejected():
    p = payload()
    p["bids"] = [[102, 1]]
    with pytest.raises(ValueError, match="crossed"):
        parse_snapshot(p)


@pytest.mark.parametrize("qty", [0, -1, float("nan"), float("inf")])
def test_invalid_size(qty):
    with pytest.raises(ValueError):
        sweep_snapshot(parse_snapshot(payload()), "BUY", qty)


def capture_record():
    text = json.dumps(payload())
    return {"symbol": "BTCUSDT", "request_started_utc": "2026-11-21T10:00:00+00:00",
            "received_utc": "2026-11-21T10:00:01+00:00", "response_text": text,
            "response_sha256": hashlib.sha256(text.encode()).hexdigest()}


def test_offline_report_deduplicates_and_preserves_censoring(tmp_path):
    source = tmp_path / "snapshots.jsonl"
    record = capture_record()
    source.write_text((json.dumps(record) + "\n") * 2, encoding="utf-8")
    report = analyse(source, tmp_path / "result", [1, 10])
    assert report["unique_updates"] == 1
    assert report["capture_records"] == 2
    assert report["summary"][1]["n_complete"] == 0
    assert report["summary"][1]["mean_full_cost_bps"] is None
    assert (tmp_path / "result" / "depth_profiles.csv").exists()
    record["response_text"] += " "
    source.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        analyse(source, tmp_path / "result", [1])


def test_collector_keeps_response_and_never_overwrites(tmp_path, monkeypatch):
    import io

    text = json.dumps(payload()).encode()
    calls = []

    def open_url(url, timeout):
        calls.append(url)
        return io.BytesIO(text)

    monkeypatch.setattr("urllib.request.urlopen", open_url)
    target = tmp_path / "capture.jsonl"
    collect(target, "BTCUSDT", 1, 5, 1000)
    saved = json.loads(target.read_text())
    assert saved["response_text"].encode() == text
    assert saved["response_sha256"] == hashlib.sha256(text).hexdigest()
    assert "symbol=BTCUSDT&limit=1000" in calls[0]
    with pytest.raises(FileExistsError):
        collect(target, "BTCUSDT", 1, 5, 1000)
