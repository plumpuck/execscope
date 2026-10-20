import pandas as pd
import pytest

from execscope.explain.facts import flatten_facts
from execscope.explain.verify import extract_numbers, ungrounded_numbers
from execscope.explain.writer import explain
from execscope.service import db

SUMMARY = {
    "algos": {
        "oneshot": {"n": 20, "fill_rate": 1.0, "vs_vwap_bps": {"mean": 0.4488, "ci_low": -0.30, "ci_high": 1.20}},
        "twap": {"n": 20, "fill_rate": 1.0, "vs_vwap_bps": {"mean": 0.0638, "ci_low": -0.25, "ci_high": 0.44}},
    },
    "paired_vs_baseline": {"twap": {"vs_vwap_bps": {"mean_diff": -0.385, "ci_low": -0.9, "ci_high": 0.2, "sign_test_p": 0.125}}},
}


def test_extract_numbers_handles_signs_commas_decimals():
    got = [(raw, v, d) for raw, v, d in extract_numbers("cost −1.76 bp, $244,200 and 18 fills")]
    assert (("-1.76"), -1.76, 2) in [(r.replace("−", "-"), v, d) for r, v, d in got]
    assert any(v == 244200.0 for _, v, _ in got)


def test_template_report_is_fully_grounded():
    e = explain(SUMMARY)
    assert e.verified and not e.used_fallback and "twap" in e.text


def test_hallucinated_number_is_caught_and_replaced():
    def liar(summary, facts):
        return "TWAP saves 7.31 bp versus one-shot, a huge win."
    e = explain(SUMMARY, writer=liar)
    assert e.used_fallback and "7.31" in e.rejected_numbers
    assert "7.31" not in e.text and e.verified


def test_rounded_numbers_match_and_wrong_rounding_does_not():
    facts = flatten_facts(SUMMARY)
    assert ungrounded_numbers("oneshot costs 0.45 bp", facts) == []
    assert ungrounded_numbers("oneshot costs 0.55 bp", facts) == ["0.55"]


def _table():
    return pd.DataFrame([
        {"parent": 0, "label": "oneshot", "start": "t0", "filled_qty": 10, "target_qty": 10, "vs_arrival_bps": 1.0, "vs_vwap_bps": 2.0, "vs_close_bps": 0.0, "is_total_bps": 1.0, "cost_usd": 5.0},
        {"parent": 0, "label": "twap", "start": "t0", "filled_qty": 10, "target_qty": 10, "vs_arrival_bps": 0.5, "vs_vwap_bps": 1.0, "vs_close_bps": 0.0, "is_total_bps": 0.5, "cost_usd": 2.0},
        {"parent": 1, "label": "oneshot", "start": "t1", "filled_qty": 10, "target_qty": 10, "vs_arrival_bps": 1.0, "vs_vwap_bps": 4.0, "vs_close_bps": 0.0, "is_total_bps": 1.0, "cost_usd": 5.0},
        {"parent": 1, "label": "twap", "start": "t1", "filled_qty": 10, "target_qty": 10, "vs_arrival_bps": 0.5, "vs_vwap_bps": float("nan"), "vs_close_bps": 0.0, "is_total_bps": 0.5, "cost_usd": 2.0},
    ])


def test_db_roundtrip_and_leaderboard():
    conn = db.connect(":memory:")
    exp_id = db.save_experiment(conn, "demo", {"a": 1}, {"git": "x"}, SUMMARY, _table())
    got = db.get_experiment(conn, exp_id)
    assert got["name"] == "demo" and got["summary"] == SUMMARY and got["config"] == {"a": 1}
    assert [e["id"] for e in db.list_experiments(conn)] == [exp_id]
    assert len(db.get_runs(conn, exp_id)) == 4
    board = {r["label"]: r for r in db.leaderboard(conn, exp_id)}
    assert board["oneshot"]["avg_vs_vwap_bps"] == pytest.approx(3.0)
    assert board["twap"]["avg_vs_vwap_bps"] == pytest.approx(1.0)   # NULL (NaN) ignored by AVG
    assert db.get_experiment(conn, 999) is None
