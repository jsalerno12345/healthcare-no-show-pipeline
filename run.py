"""
One entry point for the whole pipeline. Works the same on Windows, Mac and Linux.

    python run.py simulate   # build messy clinic export files from the Kaggle data
    python run.py load       # load those files into the DuckDB warehouse (raw layer)
    python run.py dbt        # build and test the dbt models
    python run.py all        # all three, in order
    python run.py reset      # delete generated files and the warehouse, start over
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DBT_DIR = ROOT / "dbt"


def simulate() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "simulate_clinic_exports.py")], check=True)


def load() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "load_raw.py")], check=True)


def dbt() -> None:
    # Run from the project root so the warehouse path in profiles.yml resolves.
    subprocess.run(
        ["dbt", "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)],
        check=True,
        cwd=ROOT,
    )


def reset() -> None:
    shutil.rmtree(ROOT / "data" / "clinic_exports", ignore_errors=True)
    for f in (ROOT / "data").glob("warehouse.duckdb*"):
        f.unlink()
    print("Reset complete.")


STEPS = {"simulate": simulate, "load": load, "dbt": dbt, "reset": reset}

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "all":
        simulate()
        load()
        dbt()
    elif step in STEPS:
        STEPS[step]()
    else:
        raise SystemExit(__doc__)
