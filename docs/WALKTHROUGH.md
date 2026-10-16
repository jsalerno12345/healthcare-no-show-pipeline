# Walkthrough and interview prep

Read this before any interview where you mention the project. Each section covers
what the piece does, why it's built that way, and the question you'll get about it.

---

## The 30-second pitch

"I built a pipeline that takes nightly appointment files from three clinic systems,
each formatted differently, and turns them into a trustworthy no-show dashboard. It
loads files idempotently, standardizes statuses through a mapping table, flags
anything it doesn't recognize, and runs 35 data tests, including one that proves no
appointment is lost or double-counted. Dagster runs it nightly and alerts if a clinic's
file is missing or its size spikes. The interesting finding: SMS reminders look
harmful in the raw data, but that's confounding by booking lead time. Adjusted,
they cut no-shows by about 5 points."

---

## 1. The messy data — `scripts/simulate_clinic_exports.py`
Turns one clean Kaggle file into 82 nightly files from three fake systems with
different formats, codes, duplicates and one re-sent file.

**Q: Is this real data?** "The appointments are real and anonymized, from public clinics in
Brazil. I simulated the multi-system mess because that's the actual problem at work, and
I can't share work data. The README says exactly what's simulated."

## 2. Raw loading — `scripts/load_raw.py`
- Every column loads as **text**. Casting happens later, in dbt, where it's tested.
- Every row gets `_source_file` and `_loaded_at` (**lineage**).
- `raw.load_manifest` stores a **SHA-256 hash** per file.

**Q: What happens if the job runs twice?** "Nothing. The manifest says the file's already loaded."
**Q: What if a clinic re-sends yesterday's file under a new name?** "Same hash, so it's skipped and logged."
**Q: Why load as text?** "If a clinic sends 'N/A' in an age column, a typed load fails at 2am.
Text never fails, and dbt tests tell me what's wrong."

## 3. Staging — `dbt/models/staging/`
One model per system, all producing the same columns. Pattern: rename → cast → map → flag.
- **System B:** quoted column names, US dates, `lower(trim())` before the mapping join,
  and **dedupe** with `qualify row_number() over (partition by "Appt ID" ...) = 1`.
- **System C:** day-first dates, Y/N attended flag.
- **Mapping seed** (`seeds/status_mapping.csv`): the bridge table from raw to standard status.

**Q: How did you handle duplicates, and how do you know it worked?** "Window function keeps one
row per appointment ID, and a `unique` test on `appointment_id` fails the build if any slip through."
**Q: What about status codes you've never seen?** "Left join to the mapping; no match means
`unmapped`. They show on the dashboard instead of disappearing or being guessed."
**Q: Is LWBS a no-show?** "Left without being seen: they showed up, so it's not a no-show, but
they weren't treated either. That's a business decision, so I excluded it from the rate and
surfaced the count. I'd ask clinical ops to define it."

## 4. Intermediate and marts — `dbt/models/intermediate/`, `dbt/models/marts/`
- `int_appointments` unions the three systems and adds lead time, weekday and flags.
- `fct_appointments` is the clean table everything reads from.
- `mart_no_show_daily` (day × clinic × provider), `_by_clinic`, `_by_weekday`, `mart_data_quality`.
- The rate is defined **once** in `macros/no_show_metrics.sql`.

**Q: What's your denominator?** "Appointments with a known outcome: arrived plus no-show.
Unmapped are excluded and reported separately."
**Q: How do you roll up daily rates to monthly?** "Sum the counts and divide again. Averaging
daily rates over-weights small days."
**Q: How do you know you didn't lose rows?** "`tests/assert_no_appointments_lost.sql` compares
distinct IDs in raw to rows in the fact table. 110,527 in, 110,527 out."

## 5. Tests — 35 of them
`unique`, `not_null`, `accepted_values` on every staging model and mart; custom `valid_age`
(warn) and `rate_between_0_and_1`; the reconciliation test. One expected **WARN**: a real
negative age in the source data.

**Q: Why warn instead of fail on age?** "One bad age shouldn't block leadership's dashboard. A
duplicate ID or a lost row should, because those corrupt the metric itself."

## 6. Orchestration — `orchestration/definitions.py` + `scripts/quality_checks.py`
Dagster assets: exports → raw → dbt → analysis → dashboard. Two asset checks on raw:
- **latest_file_arrived:** every system sent a file for the latest day.
- **row_count_spike:** latest file isn't >2× or <0.5× the median of the previous 7.
Schedule: 6:00am ET daily, so the dashboard is ready by 7.

**Q: It's 6:30am, Clinic 212's file is missing and Clinic 87's doubled. What happens?** "Both
checks fail and alert. The pipeline still builds, but the dashboard's data quality section
shows what's incomplete, so nobody makes decisions on a silently wrong number."

## 7. The SMS analysis — `analysis/sms_reminder_analysis.py`
1. **Naive:** 27.6% no-show with SMS vs 16.7% without. Looks harmful.
2. **Why:** reminders only go to bookings 3+ days ahead. Same-day visits (4.7% no-show) never get one.
3. **Like with like:** within every lead-time window, reminded patients miss fewer visits.
4. **Logistic regression** on 3+ day bookings, controlling for lead time, age and sex:
   odds ratio 0.77 (0.74–0.79), about **−5.4 percentage points**.

**Q: Is that causal?** "No, it's observational. Something like having a valid phone number could
still confound it. I'd recommend an A/B test: randomly hold out reminders for a small group."
**Q: What would you recommend to the clinic?** "Keep reminders, and test sending them for
1–2 day bookings. That window has a 23% no-show rate and gets no reminders today."

## 8. Dashboard — `scripts/build_dashboard.py`
One self-contained HTML file: KPIs, daily trend, weekday, best/worst clinics, the SMS chart,
and the data quality table. Light and dark mode, works on a phone, every chart has a table view.

---

## Things to be honest about
- You built this with AI assistance. Say so if asked: "I use agents to build, and I review
  and test everything. Here's how I verified it: 35 tests and a reconciliation check."
- Limitation you can volunteer: a *corrected* re-send under the same file name would load again.
  The unique test catches it for Systems A and C, but System B's dedupe would keep the old copy.
  The real fix is "latest version wins" per appointment, ordered by load time.
