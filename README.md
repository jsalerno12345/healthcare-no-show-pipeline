# Healthcare No-Show Pipeline

**Turning messy appointment exports from three clinic systems into a trustworthy daily no-show dashboard, and finding out whether SMS reminders actually work.**

Missed appointments cost clinics revenue and delay care. Leadership wants a daily no-show rate by clinic, provider and day of week. The hard part isn't the division. It's that every clinic system sends data differently, and a dashboard built on inconsistent data is confidently wrong.

This project builds the whole pipeline: ingest → clean → standardize → test → schedule → serve → analyze.

**[Live dashboard](https://jsalerno12345.github.io/healthcare-no-show-pipeline/reports/dashboard.html)** · **[SMS reminder analysis](reports/sms_reminder_analysis.md)**

---

## Key findings

- **20.2% of appointments are missed** (22,288 of 110,527), ranging from 14.6% to 28.9% across clinics (those with 100+ visits).
- **SMS reminders look harmful in the raw data, but they help.** Reminded patients miss 27.6% of visits vs 16.7% without a reminder. That's confounding: reminders only go to visits booked 3+ days ahead, which are missed more often anyway. Compared within the same booking window, reminders lower no-shows every time. Adjusted estimate: **−5.4 percentage points** (odds ratio 0.77, 95% CI 0.74–0.79).
- **Opportunity:** visits booked 1–2 days ahead have a 22.7% no-show rate and get no reminders at all.
- **The pipeline caught 538 data problems** before they reached the dashboard: 392 duplicate rows, 1 re-sent file, 145 unrecognized status codes, plus invalid ages and impossible booking dates.

## The problem, in data

Real clinic data is messy, so the project recreates that mess from a public dataset of ~110,000 real (anonymized) appointments.

| | System A (EHR) | System B (front desk) | System C (legacy) |
|---|---|---|---|
| Format | CSV | CSV | Pipe-delimited `.txt` |
| Dates | `2016-05-17` | `05/17/2016` | `17-May-2016` |
| "No show" looks like | `2` | `No Show`, `NS`, `noshow`, `No-Show`… | `ATTENDED = N` |
| Known issues | — | ~1% duplicate rows, unmapped codes (`LWBS`, `?`, blank), one file re-sent under a new name | a negative patient age (real, from the source) |

## Architecture

```
clinic exports (82 nightly files)
      │
      ▼
scripts/load_raw.py ─────► raw            text only, untouched, + source file & load time
      │                    load_manifest  SHA-256 per file → re-runs & re-sends are safe
      │
      ├─ quality checks ── did every system send today's file? any row-count spike?
      ▼
dbt staging ─────────────► staging        per system: rename, type, dedupe, map statuses
      ▼
dbt intermediate ────────► intermediate   all systems unioned + lead time, weekday
      ▼
dbt marts ───────────────► reporting      fct_appointments, no-show by day/clinic/
      │                                   provider/weekday, data quality scorecard
      ▼
analysis + dashboard ────► reports/       SMS analysis (logistic regression), HTML dashboard

Orchestrated by Dagster: nightly at 6:00am ET, with the quality checks as asset checks.
35 dbt tests, including a reconciliation test that every raw appointment lands exactly once.
```

Runs entirely on a laptop: [DuckDB](https://duckdb.org/) warehouse, [dbt](https://www.getdbt.com/) transformations, [Dagster](https://dagster.io/) orchestration. No cloud account needed.

## Design decisions

- **Define the metric first.** No-show rate = no-shows ÷ appointments with a known outcome. Is `LWBS` (left without being seen) a no-show? The patient came but wasn't seen, so it's neither a clean "arrived" nor a "no-show." It's left **unmapped and excluded from the rate**, and counted on the dashboard until the business decides.
- **Raw stays raw.** Files load as text exactly as sent. Any cleaning decision can be changed and reprocessed later.
- **Idempotent loads.** A manifest stores each file's SHA-256 hash. Running the loader twice loads nothing new; a re-sent file with a new name is detected and skipped.
- **Mapping as data, not code.** Status translations live in [`dbt/seeds/status_mapping.csv`](dbt/seeds/status_mapping.csv). Adding a new code is a one-line change a non-engineer can review.
- **Flag, don't drop.** Unrecognized values become `visit_status = 'unmapped'`, so problems stay visible instead of silently disappearing.
- **One metric definition.** The rate is defined once in a dbt macro ([`no_show_metrics`](dbt/macros/no_show_metrics.sql)) and reused by every mart, so the numbers can't drift apart.
- **Sum counts, never average rates.** Marts carry counts so any roll-up recomputes the rate correctly.
- **Warn vs fail.** A bad age warns (report it, keep going). A duplicate appointment ID or a lost row fails the build.
- **Right-sized tools.** ~4,000 appointments a day fits easily on one machine. No Spark, no cluster.

## Run it

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**Get the data:** download "Medical Appointment No Shows" from Kaggle and save it as `data/source/KaggleV2-May-2016.csv`.

```bash
python run.py all       # simulate → load → checks → dbt build → analysis → dashboard
python run.py reset     # start over
```

Then open `reports/dashboard.html`.

**With the scheduler UI:**

```bash
dagster dev -f orchestration/definitions.py     # then open http://localhost:3000
```

## Project layout

```
run.py                          one command for everything
scripts/
  simulate_clinic_exports.py    builds the messy clinic files from the Kaggle data
  load_raw.py                   idempotent raw loader with file manifest
  quality_checks.py             missing-file and row-spike checks
  build_dashboard.py            renders reports/dashboard.html
dbt/
  seeds/status_mapping.csv      raw status → standard status
  models/staging/               one model per clinic system
  models/intermediate/          all systems unioned
  models/marts/                 reporting tables
  macros/no_show_metrics.sql    the metric, defined once
  tests/                        custom and reconciliation tests
orchestration/definitions.py    Dagster assets, checks and nightly schedule
analysis/sms_reminder_analysis.py
reports/                        dashboard + analysis output
```

## Limitations and next steps

- The SMS finding is observational. The right next step is an A/B test: randomly withhold reminders for a small share of patients.
- If a clinic re-sends a *corrected* file under the same name, the loader loads it again. For Systems A and C the unique test fails the build; for System B the dedupe keeps the first (outdated) copy. The proper fix is a "latest version wins" rule per appointment.
- Next: LLM-assisted mapping of new status codes, with accuracy measured against hand-labeled examples.

## Data and attribution

Source: "Medical Appointment No Shows" (Kaggle), ~110k appointments from public clinics in Vitória, Brazil, April–June 2016. Not redistributed here.

**Simulated for this project** (not in the original data): the split into three clinic systems, provider IDs, status spelling variants, duplicate rows and the re-sent file. All simulation is seeded and reproducible.
