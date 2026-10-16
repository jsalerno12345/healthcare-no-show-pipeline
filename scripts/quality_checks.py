"""
Operational checks that run every night before the dashboard refreshes.
They answer the 6:30am question: "Can we trust this morning's numbers?"

    1. Did every clinic system send a file for the latest day?
    2. Is any system's latest file wildly bigger or smaller than usual?

Plain functions, so they run from the command line (python run.py checks)
and inside Dagster (orchestration/definitions.py) with the same logic.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "data" / "clinic_exports"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
SYSTEMS = ("system_a", "system_b", "system_c")
SPIKE_RATIO = 2.0  # alert if a file is > 2x or < 0.5x its recent median


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _file_dates(system: str) -> set[str]:
    dates = set()
    for f in (EXPORTS / system).glob("*"):
        m = re.search(r"(\d{8})", f.name)
        if m:
            dates.add(m.group(1))
    return dates


def check_all_systems_sent_latest_file() -> CheckResult:
    by_system = {s: _file_dates(s) for s in SYSTEMS}
    latest = max(d for dates in by_system.values() for d in dates)
    missing = [s for s, dates in by_system.items() if latest not in dates]
    if missing:
        return CheckResult(
            "latest_file_arrived", False,
            f"No file for {latest} from: {', '.join(missing)}. "
            "Dashboard numbers for that day are incomplete.",
        )
    return CheckResult("latest_file_arrived", True, f"All systems sent a file for {latest}.")


def check_row_count_spike(window: int = 7) -> CheckResult:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    rows = con.execute(
        """
        select system, file_name, row_count
        from raw.load_manifest
        where status = 'loaded'
        order by system, file_name
        """
    ).fetchall()
    con.close()
    problems, notes = [], []
    for system in SYSTEMS:
        counts = [(f, n) for s, f, n in rows if s == system]
        if len(counts) <= window:
            continue
        latest_file, latest_n = counts[-1]
        baseline = statistics.median(n for _, n in counts[-window - 1:-1])
        ratio = latest_n / baseline if baseline else float("inf")
        line = f"{system}: {latest_file} has {latest_n:,} rows vs median {baseline:,.0f} ({ratio:.1f}x)"
        notes.append(line)
        if ratio > SPIKE_RATIO or ratio < 1 / SPIKE_RATIO:
            problems.append(line)
    if problems:
        return CheckResult("row_count_spike", False, "Unusual file size: " + "; ".join(problems))
    return CheckResult("row_count_spike", True, "; ".join(notes) or "Not enough history yet.")


def run_all() -> list[CheckResult]:
    return [check_all_systems_sent_latest_file(), check_row_count_spike()]


if __name__ == "__main__":
    failed = False
    for r in run_all():
        print(f"[{'PASS' if r.passed else 'ALERT'}] {r.name}: {r.detail}")
        failed |= not r.passed
    raise SystemExit(1 if failed else 0)
