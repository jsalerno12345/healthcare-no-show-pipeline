# Healthcare No-Show Pipeline

**Turning messy appointment exports from three clinic systems into a trustworthy daily no-show dashboard.**

Missed appointments cost clinics revenue and delay care. Leadership wants a daily no-show rate by clinic, provider and day of week. The hard part isn't the division. It's that every clinic system sends its data differently, and a dashboard built on inconsistent data is confidently wrong.

This project builds the pipeline end to end: ingest, clean, standardize, test, and serve.

> **Status:** 🚧 In progress — Week 1 of 6 complete (raw ingestion + first staging model). See [Roadmap](#roadmap).

---

## The problem, in data

Real clinic data is messy, so the project starts by recreating that mess from a public dataset of ~110,000 real (anonymized) appointments.

| | System A (EHR) | System B (front desk) | System C (legacy) |
|---|---|---|---|
| Format | CSV | CSV | Pipe-delimited `.txt` |
| Dates | `2016-05-17` | `05/17/2016` | `17-May-2016` |
| "No show" looks like | `2` | `No Show`, `NS`, `noshow`, `No-Show`… | `ATTENDED = N` |
| Known issues | — | ~1% duplicate rows, unmapped codes (`LWBS`, `?`, blank), one file re-sent under a new name | a negative patient age (real, from the source data) |

## Architecture

```
clinic exports (nightly files)
        │
        ▼
  scripts/load_raw.py ──► raw schema        all text, untouched, with source file + load time
        │                   load_manifest   content hash per file → re-runs and re-sends are safe
        ▼
  dbt staging models ──► staging schema     renamed, typed, statuses mapped through a seed table
        │                                     unknown statuses flagged, never guessed
        ▼
  dbt marts (Week 3) ──► reporting schema   no-show rate by clinic / provider / weekday
        │
        ▼
  dashboard (Week 5)
```

Everything runs locally on [DuckDB](https://duckdb.org/) — no cloud account needed.

## Design decisions

- **Define the metric first.** "No-show" means different things in different systems. Is `LWBS` (left without being seen) a no-show? It's left unmapped and flagged until the business decides, rather than guessed.
- **Raw stays raw.** Files load as text exactly as sent, so any cleaning decision can be changed and reprocessed later.
- **Idempotent loads.** A manifest stores each file's SHA-256 hash. Running the loader twice loads nothing new; a re-sent file with a new name is detected and skipped.
- **Mapping as data, not code.** Status translations live in `dbt/seeds/status_mapping.csv`. Adding a new code is a one-line change a non-engineer can review.
- **Flag, don't drop.** Unrecognized values become `visit_status = 'unmapped'` with `is_unmapped_status = true`, so data quality is visible on the dashboard instead of silently lost.
- **Right-sized tools.** ~4,000 appointments a day (110k total) fits easily on one machine. No Spark, no cluster.

## Run it

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

**Get the data:** download "Medical Appointment No Shows" from Kaggle and save it as `data/source/KaggleV2-May-2016.csv`.

```bash
python run.py all     # simulate exports → load raw → dbt build (models + tests)
python run.py reset   # start over
```

## Roadmap

- [x] **Week 1** — Simulated clinic exports, idempotent raw loader, dbt project, System A staging model + tests
- [ ] **Week 2** — Staging for Systems B and C: date parsing, deduplication, status mapping, unmapped-status reporting
- [ ] **Week 3** — Unified appointments model and no-show marts by clinic, provider and weekday, with tests
- [ ] **Week 4** — Orchestration with Dagster: nightly schedule, alert when a clinic's file is late or its row count spikes
- [ ] **Week 5** — Dashboard + write-up
- [ ] **Week 6** — Analysis: do SMS reminders reduce no-shows once booking lead time is accounted for?
- [ ] **Stretch** — LLM-assisted mapping of unknown status values, with measured accuracy against hand labels

## Data and attribution

Source: "Medical Appointment No Shows" (Kaggle), ~110k appointments from public clinics in Vitória, Brazil, 2016. Not redistributed here.

**Simulated for this project** (not in the original data): the split into three clinic systems, provider IDs, status spelling variants, duplicate rows and the re-sent file. All simulation is seeded and reproducible (`scripts/simulate_clinic_exports.py`).
