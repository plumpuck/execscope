-- ExecScope result store. Plain SQL that works in SQLite and PostgreSQL.
CREATE TABLE IF NOT EXISTS experiments (
    id            INTEGER PRIMARY KEY,          -- PostgreSQL: use BIGSERIAL
    name          TEXT NOT NULL,
    created_utc   TEXT NOT NULL,
    config_json   TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    summary_json  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY,
    experiment_id    INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    parent           INTEGER NOT NULL,          -- parent-order index inside the experiment
    label            TEXT NOT NULL,             -- algorithm label
    start_ts         TEXT NOT NULL,
    filled_qty       REAL NOT NULL,
    target_qty       REAL NOT NULL,
    vs_arrival_bps   REAL,
    vs_vwap_bps      REAL,
    vs_close_bps     REAL,
    is_total_bps     REAL,
    cost_usd         REAL
);
CREATE INDEX IF NOT EXISTS runs_by_experiment ON runs (experiment_id, label);
