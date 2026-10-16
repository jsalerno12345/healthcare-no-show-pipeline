"""
Dagster orchestration: runs the pipeline every morning and checks that the
data can be trusted before anyone looks at the dashboard.

    clinic_exports -> raw_appointments -> dbt_models -> sms_analysis -> dashboard
                           |
                           +-- checks: latest file arrived? row count normal?

Run the UI locally:    dagster dev -f orchestration/definitions.py
Then open http://localhost:3000, click "Materialize all", and see the checks.

In production the schedule below would run at 6:00am so the dashboard is ready
by 7:00am. `clinic_exports` stands in for "files arrive from the clinics";
here it regenerates the simulated files.
"""


import subprocess
import sys
from pathlib import Path

import dagster as dg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quality_checks  # noqa: E402


def _run(*args: str) -> str:
    result = subprocess.run(
        [*args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise dg.Failure(description=result.stdout[-2000:] + result.stderr[-2000:])
    return result.stdout


@dg.asset(group_name="ingest", description="Nightly export files from the three clinic systems.")
def clinic_exports(context: dg.AssetExecutionContext) -> None:
    context.log.info(_run(sys.executable, "scripts/simulate_clinic_exports.py"))


@dg.asset(
    group_name="ingest",
    deps=[clinic_exports],
    description="Files loaded as-is into the raw schema, idempotently, with lineage.",
)
def raw_appointments(context: dg.AssetExecutionContext) -> None:
    context.log.info(_run(sys.executable, "scripts/load_raw.py"))


@dg.asset_check(asset=raw_appointments, description="Every clinic system sent a file for the latest day.")
def latest_file_arrived() -> dg.AssetCheckResult:
    r = quality_checks.check_all_systems_sent_latest_file()
    return dg.AssetCheckResult(passed=r.passed, description=r.detail)


@dg.asset_check(asset=raw_appointments, description="No system's latest file is >2x or <0.5x its recent median.")
def row_count_spike() -> dg.AssetCheckResult:
    r = quality_checks.check_row_count_spike()
    return dg.AssetCheckResult(passed=r.passed, description=r.detail)


@dg.asset(
    group_name="transform",
    deps=[raw_appointments],
    description="dbt build: staging, marts and all data tests.",
)
def dbt_models(context: dg.AssetExecutionContext) -> None:
    context.log.info(
        _run("dbt", "build", "--project-dir", "dbt", "--profiles-dir", "dbt")[-3000:]
    )


@dg.asset(
    group_name="serve",
    deps=[dbt_models],
    description="SMS reminder analysis (confounding-adjusted).",
)
def sms_analysis(context: dg.AssetExecutionContext) -> None:
    context.log.info(_run(sys.executable, "analysis/sms_reminder_analysis.py"))


@dg.asset(
    group_name="serve",
    deps=[dbt_models, sms_analysis],
    description="Static HTML dashboard built from the reporting marts.",
)
def dashboard(context: dg.AssetExecutionContext) -> None:
    context.log.info(_run(sys.executable, "scripts/build_dashboard.py"))


nightly_job = dg.define_asset_job("nightly_pipeline", selection=dg.AssetSelection.all())

nightly_schedule = dg.ScheduleDefinition(
    job=nightly_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/New_York",
)

defs = dg.Definitions(
    assets=[clinic_exports, raw_appointments, dbt_models, sms_analysis, dashboard],
    asset_checks=[latest_file_arrived, row_count_spike],
    jobs=[nightly_job],
    schedules=[nightly_schedule],
)
