"""Load saved experiment folders (rows.csv + summary.json + manifest.json) into the SQLite result store.

    python -m execscope.service.ingest "results/e*" --db execscope.db

Folders without rows.csv (such as a results root) are ignored. A name already in the store is skipped.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from execscope.data.binance import expand_paths
from execscope.service import db


def ingest_folder(conn, folder: Path) -> int | None:
    """Return the new experiment id, or None if `folder` is not a run or is already stored."""
    if not (folder / "rows.csv").exists() or folder.name in {e["name"] for e in db.list_experiments(conn)}:
        return None
    man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return db.save_experiment(conn, folder.name, man["config"], man, summary, pd.read_csv(folder / "rows.csv"))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folders", nargs="+")
    p.add_argument("--db", default="execscope.db")
    a = p.parse_args(argv)
    conn = db.connect(a.db)
    for folder in map(Path, expand_paths(a.folders)):
        exp_id = ingest_folder(conn, folder)
        print(f"{folder}: {'skipped' if exp_id is None else f'experiment {exp_id}'}")


if __name__ == "__main__":
    main()
