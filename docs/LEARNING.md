# Learning log

Your private study guide for this project. The rule: **you can explain every line.** If you can't, that's the next thing to learn — ask an agent to walk you through it, then break it on purpose.

---

## Week 1 — what was built, and why

### 1. `scripts/simulate_clinic_exports.py` — making the mess
Takes one clean Kaggle file and writes ~82 nightly files from three fake clinic systems, each with its own quirks (see the README table).

**Be able to say:** "Real data never arrives clean, so I recreated the problems I see at work: inconsistent codes, date formats, duplicates and re-sent files."

**Try it:** open one file from each folder in `data/clinic_exports/`. Spot three differences.

### 2. `scripts/load_raw.py` — the raw layer
- Loads every column **as text** (`all_varchar = true`). Why? If you cast on load and a clinic sends `"N/A"` in an age column, the whole load fails at 2am. Text never fails; cleaning happens in dbt, where it's tested.
- Adds `_source_file` and `_loaded_at` to every row. Why? When a number looks wrong, you can trace it to the exact file.
- Keeps `raw.load_manifest` with a **SHA-256 hash** of each file. Why? Re-running is safe (nothing double-loads), and System B's `_RESEND` file is caught because its contents match a file already loaded.

**Try it:** run `python run.py load` twice. Second run: `already_loaded=81`. That's idempotency.

**Interview question you can now answer:** *"What happens if the job runs twice?"*

### 3. dbt — the transformation layer
- `models/staging/_sources.yml` declares the raw tables and tests them (`not_null` on IDs).
- `seeds/status_mapping.csv` is the **bridge table** from your mock interview: raw value → standard status.
- `models/staging/stg_system_a__appointments.sql` is the worked example. Read its header comment: rename → cast → map → flag.
- `tests/generic/valid_age.sql` is a custom test. The source data really has one negative age (it lands in System C). It's set to **warn**, not fail. Why? A bad age shouldn't block the whole dashboard; it should be reported. System A passes; when you build System C in Week 2 and add this test, you should see your first **WARN**.

**Try it:**
```bash
python run.py dbt
```
Then explore the warehouse:
```bash
python -c "import duckdb; c=duckdb.connect('data/warehouse.duckdb'); print(c.sql('select visit_status, count(*) from staging.stg_system_a__appointments group by 1'))"
```

---

## Week 2 — your turn: Systems B and C

Copy `stg_system_a__appointments.sql` and adapt it. Use an agent, but **write the plan yourself first.**

**System B** (`stg_system_b__appointments.sql`):
1. Column names have spaces → `source."Appt ID"`.
2. Dates are US format → `strptime("Appt Date", '%m/%d/%Y')`.
3. Statuses vary in case and spacing → join on `lower(trim("Visit Status"))`. The seed is already lower-case.
4. Duplicates (~400 rows) → keep one row per `Appt ID`. Look up DuckDB's `qualify row_number() over (...) = 1`.
5. Blank, `?` and `LWBS` should come out as `unmapped`. **Decide:** is LWBS a no-show? Write your reasoning in the README.

**System C** (`stg_system_c__appointments.sql`):
1. Day-first dates → `strptime(APPT_DT, '%d-%b-%Y')`.
2. `ATTENDED = 'N'` means no-show (already in the seed).

**Then:** add both to `_staging.yml` with `unique` + `not_null` on `appointment_id`. Run `python run.py dbt` until it's green.

**Done when** you can answer: *"How did you handle duplicates, and how do you know it worked?"* (Hint: the `unique` test.)

---

## Weeks 3–6 (preview)
- **3:** `int_appointments` unions the three staging models; `mart_no_show_daily` computes the rate. Decide the denominator.
- **4:** Dagster schedules the run and alerts when a clinic's file is missing or its row count doubles. (Your mock-interview follow-up question.)
- **5:** Dashboard + README write-up with findings.
- **6:** SMS reminder analysis. Naively, reminded patients look *worse*: 27.6% no-show vs 16.7% without a reminder. Find out why (hint: reminders go to appointments booked further ahead) and adjust for it.
