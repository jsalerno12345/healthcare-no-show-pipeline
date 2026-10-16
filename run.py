"""
One entry point for the whole pipeline. Works the same on Windows, Mac and Linux.

    python run.py all        # everything below, in order
    python run.py simulate   # build messy clinic export files from the Kaggle data
    python run.py load       # load those files into the DuckDB warehouse (raw layer)
    python run.py checks     # did every file arrive? any suspicious row counts?
    python run.py dbt        # build and test the dbt models (staging -> marts)
    python run.py analysis   # SMS reminder analysis -> reports/sms_reminder_analysis.md
    python run.py dashboard  # build reports/dashboard.html
    python run.py reset      # delete generated files and the warehouse, start over

For the scheduled version with a UI, see orchestration/definitions.py (Dagster).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DBT_DIR = ROOT / "dbt"


def py(script: str, check: bool = True) -> int:
    return subprocess.run([sys.executable, str(ROOT / script)], check=check, cwd=ROOT).returncode


def simulate() -> None:
    py("scripts/simulate_clinic_exports.py")


def load() -> None:
    py("scripts/load_raw.py")


def checks() -> None:
    # Alerts are printed but don't stop the run: the dashboard still builds,
    # and the data quality table shows what's wrong.
    if py("scripts/quality_checks.py", check=False) != 0:
        print("!! Quality checks raised alerts (see above). Continuing.")


def dbt() -> None:
    # Run from the project root so the warehouse path in profiles.yml resolves.
    subprocess.run(
        ["dbt", "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)],
        check=True,
        cwd=ROOT,
    )


def analysis() -> None:
    py("analysis/sms_reminder_analysis.py")


def dashboard() -> None:
    py("scripts/build_dashboard.py")


def reset() -> None:
    shutil.rmtree(ROOT / "data" / "clinic_exports", ignore_errors=True)
    for f in (ROOT / "data").glob("warehouse.duckdb*"):
        f.unlink()
    print("Reset complete.")


STEPS = {
    "simulate": simulate, "load": load, "checks": checks, "dbt": dbt,
    "analysis": analysis, "dashboard": dashboard, "reset": reset,
}
ALL = ["simulate", "load", "checks", "dbt", "analysis", "dashboard"]

if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step == "all":
        for name in ALL:
            print(f"\n=== {name} ===")
            STEPS[name]()
        print(f"\nDone. Open {ROOT / 'reports' / 'dashboard.html'} in a browser.")
    elif step in STEPS:
        STEPS[step]()
    else:
        raise SystemExit(__doc__)
