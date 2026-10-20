"""SQLite result store (schema in sql/schema.sql; the SQL is PostgreSQL-compatible)."""
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

SCHEMA = (Path(__file__).resolve().parents[3] / "sql" / "schema.sql")
_FALLBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_utc TEXT NOT NULL,
  config_json TEXT NOT NULL, manifest_json TEXT NOT NULL, summary_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  parent INTEGER NOT NULL, label TEXT NOT NULL, start_ts TEXT NOT NULL, filled_qty REAL NOT NULL, target_qty REAL NOT NULL,
  vs_arrival_bps REAL, vs_vwap_bps REAL, vs_close_bps REAL, is_total_bps REAL, cost_usd REAL);
CREATE INDEX IF NOT EXISTS runs_by_experiment ON runs (experiment_id, label);
"""
RUN_COLUMNS = ("parent", "label", "start_ts", "filled_qty", "target_qty", "vs_arrival_bps",
               "vs_vwap_bps", "vs_close_bps", "is_total_bps", "cost_usd")


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8") if SCHEMA.exists() else _FALLBACK_SCHEMA)
    return conn


def _clean(v):
    if v is None:
        return None
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


def save_experiment(conn: sqlite3.Connection, name: str, config: dict, manifest: dict,
                    summary: dict, table: pd.DataFrame) -> int:
    cur = conn.execute(
        "INSERT INTO experiments (name, created_utc, config_json, manifest_json, summary_json) VALUES (?,?,?,?,?)",
        (name, datetime.now(UTC).isoformat(timespec="seconds"),
         json.dumps(config), json.dumps(manifest), json.dumps(summary)),
    )
    exp_id = cur.lastrowid
    if exp_id is None:
        raise RuntimeError("insert did not return a row id")
    rows = [
        (exp_id, int(r["parent"]), str(r["label"]), str(r["start"]), float(r["filled_qty"]), float(r["target_qty"]),
         *(_clean(r.get(c)) for c in ("vs_arrival_bps", "vs_vwap_bps", "vs_close_bps", "is_total_bps", "cost_usd")))
        for r in table.to_dict("records")
    ]
    conn.executemany(
        "INSERT INTO runs (experiment_id, parent, label, start_ts, filled_qty, target_qty, vs_arrival_bps,"
        " vs_vwap_bps, vs_close_bps, is_total_bps, cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return exp_id


def list_experiments(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT id, name, created_utc FROM experiments ORDER BY id DESC")
    return [dict(r) for r in cur.fetchall()]


def get_experiment(conn: sqlite3.Connection, exp_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    if r is None:
        return None
    return {"id": r["id"], "name": r["name"], "created_utc": r["created_utc"],
            "config": json.loads(r["config_json"]), "manifest": json.loads(r["manifest_json"]),
            "summary": json.loads(r["summary_json"])}


def get_runs(conn: sqlite3.Connection, exp_id: int) -> list[dict]:
    cur = conn.execute(f"SELECT {', '.join(RUN_COLUMNS)} FROM runs WHERE experiment_id = ? ORDER BY parent, label", (exp_id,))
    return [dict(r) for r in cur.fetchall()]


def leaderboard(conn: sqlite3.Connection, exp_id: int) -> list[dict]:
    cur = conn.execute(
        """SELECT label, COUNT(*) AS n_parents, AVG(vs_vwap_bps) AS avg_vs_vwap_bps,
                  AVG(vs_arrival_bps) AS avg_vs_arrival_bps, AVG(is_total_bps) AS avg_is_bps,
                  AVG(filled_qty / target_qty) AS fill_rate
           FROM runs WHERE experiment_id = ? GROUP BY label ORDER BY avg_vs_vwap_bps""", (exp_id,))
    return [dict(r) for r in cur.fetchall()]
