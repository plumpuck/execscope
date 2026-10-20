"""HTTP API + dashboard over the result store.

Run:  uvicorn execscope.service.app:app --reload      (then open http://127.0.0.1:8000)
Env:  EXECSCOPE_DB  path of the SQLite file (default ./execscope.db)
"""
import os
from pathlib import Path

import pandas as pd
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from execscope.explain.writer import explain
from execscope.service import db

STATIC = Path(__file__).parent / "static"
MAX_PARENTS_PER_REQUEST = 200


class IngestPayload(BaseModel):
    """What `execscope.experiments.harness` writes: rows.csv as records + summary.json + manifest.json."""
    name: str
    rows: list[dict]
    summary: dict
    manifest: dict


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="ExecScope", version="0.2.0")
    conn = db.connect(db_path or os.environ.get("EXECSCOPE_DB", "execscope.db"))

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return (STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/experiments")
    def experiments() -> list[dict]:
        return db.list_experiments(conn)

    @app.get("/api/experiments/{exp_id}")
    def experiment(exp_id: int) -> dict:
        got = db.get_experiment(conn, exp_id)
        if got is None:
            raise HTTPException(404, "experiment not found")
        return got

    @app.get("/api/experiments/{exp_id}/rows")
    def rows(exp_id: int) -> list[dict]:
        if db.get_experiment(conn, exp_id) is None:
            raise HTTPException(404, "experiment not found")
        return db.get_runs(conn, exp_id)

    @app.get("/api/experiments/{exp_id}/leaderboard")
    def leaderboard(exp_id: int) -> list[dict]:
        if db.get_experiment(conn, exp_id) is None:
            raise HTTPException(404, "experiment not found")
        return db.leaderboard(conn, exp_id)

    @app.get("/api/experiments/{exp_id}/report")
    def report(exp_id: int) -> dict:
        got = db.get_experiment(conn, exp_id)
        if got is None:
            raise HTTPException(404, "experiment not found")
        e = explain(got["summary"])
        return {"text": e.text, "verified": e.verified, "used_fallback": e.used_fallback,
                "rejected_numbers": e.rejected_numbers}

    @app.post("/api/ingest", status_code=201)
    def ingest(payload: IngestPayload = Body(...)) -> dict:
        if not payload.rows:
            raise HTTPException(422, "rows must not be empty")
        need = {"parent", "label", "start", "filled_qty", "target_qty"}
        missing = need - set(payload.rows[0])
        if missing:
            raise HTTPException(422, f"rows missing columns: {sorted(missing)}")
        exp_id = db.save_experiment(conn, payload.name, payload.manifest.get("config", {}),
                                    payload.manifest, payload.summary, pd.DataFrame(payload.rows))
        return {"id": exp_id}

    @app.post("/api/run", status_code=201)
    def run(config: dict = Body(...)) -> dict:
        """Run an experiment on the server (needs the `backtest` extra). Capped for safety."""
        from execscope.experiments.harness import ExperimentConfig, run_experiment
        try:
            cfg = ExperimentConfig(**config)
        except TypeError as exc:
            raise HTTPException(422, str(exc)) from exc
        if cfg.n_parents > MAX_PARENTS_PER_REQUEST:
            raise HTTPException(422, f"n_parents must be <= {MAX_PARENTS_PER_REQUEST}")
        if not cfg.data.startswith("synthetic:"):
            raise HTTPException(422, "server-side runs accept synthetic data only; ingest results from your machine instead")
        table, summary, manifest = run_experiment(cfg)
        exp_id = db.save_experiment(conn, cfg.name, manifest["config"], manifest, summary, table)
        return {"id": exp_id}

    return app


app = create_app()
