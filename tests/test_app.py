import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from execscope.service.app import create_app  # noqa: E402

SUMMARY = {
    "algos": {"oneshot": {"n": 2, "fill_rate": 1.0, "vs_vwap_bps": {"mean": 3.0, "ci_low": 2.0, "ci_high": 4.0}},
              "twap": {"n": 2, "fill_rate": 1.0, "vs_vwap_bps": {"mean": 1.0, "ci_low": 0.5, "ci_high": 1.5}}},
    "paired_vs_baseline": {},
}
ROWS = [{"parent": p, "label": lab, "start": "t", "filled_qty": 10, "target_qty": 10,
         "vs_arrival_bps": 1.0, "vs_vwap_bps": v, "vs_close_bps": 0.0, "is_total_bps": 1.0, "cost_usd": 1.0}
        for p in (0, 1) for lab, v in (("oneshot", 3.0), ("twap", 1.0))]


def client():
    return TestClient(create_app(":memory:"))


def test_health_and_dashboard():
    c = client()
    assert c.get("/health").json() == {"status": "ok"}
    page = c.get("/")
    assert page.status_code == 200 and "ExecScope" in page.text


def test_ingest_then_read_back_everything():
    c = client()
    r = c.post("/api/ingest", json={"name": "demo", "rows": ROWS, "summary": SUMMARY, "manifest": {"data": "x", "config": {"seed": 0}}})
    assert r.status_code == 201
    i = r.json()["id"]
    assert [e["name"] for e in c.get("/api/experiments").json()] == ["demo"]
    assert c.get(f"/api/experiments/{i}").json()["summary"] == SUMMARY
    assert len(c.get(f"/api/experiments/{i}/rows").json()) == 4
    board = {b["label"]: b for b in c.get(f"/api/experiments/{i}/leaderboard").json()}
    assert board["twap"]["avg_vs_vwap_bps"] == pytest.approx(1.0)
    rep = c.get(f"/api/experiments/{i}/report").json()
    assert rep["verified"] and "twap" in rep["text"]


def test_errors_are_clean():
    c = client()
    assert c.get("/api/experiments/99").status_code == 404
    assert c.post("/api/ingest", json={"name": "x", "rows": [], "summary": {}, "manifest": {}}).status_code == 422
    bad = c.post("/api/ingest", json={"name": "x", "rows": [{"parent": 0}], "summary": {}, "manifest": {}})
    assert bad.status_code == 422 and "missing" in bad.text


def test_server_side_run_is_limited_and_synthetic_only():
    c = client()
    assert c.post("/api/run", json={"name": "x", "n_parents": 500}).status_code == 422
    assert c.post("/api/run", json={"name": "x", "data": "C:/secret.csv"}).status_code == 422
    assert c.post("/api/run", json={"name": "x", "bogus": 1}).status_code == 422


def test_server_side_run_end_to_end():
    pytest.importorskip("nautilus_trader")
    c = client()
    r = c.post("/api/run", json={"name": "api_run", "n_parents": 3, "horizon_bars": 10, "qty": 50, "n_boot": 100,
                                 "algos": [{"name": "oneshot"}, {"name": "twap"}]})
    assert r.status_code == 201
    assert c.get(f"/api/experiments/{r.json()['id']}/report").json()["verified"]
